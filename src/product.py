"""Student calendar, push preferences, admin analytics and review API."""
from __future__ import annotations
import json,os,re,time,uuid,logging
from datetime import datetime,timezone
from urllib.parse import urlsplit
from typing import Literal
from fastapi import Request,Query
from pydantic import BaseModel,Field,StrictStr,StrictInt
from src.product_auth import router,require_admin,require_user,user_for,error,unlock_account
from src.product_db import db
from src.product_seed import SOURCES
METHODS=("1a","1b","2")
OFFSETS=(0,1,4,7)
log=logging.getLogger(__name__)
def record_question(request,message,result,latency_ms):
    """Signed-in users only; never save obvious credential-bearing input."""
    try:
        user=user_for(request)
        if not user:return
        if re.search(r"password|mật khẩu|api\s*key|secret|token|otp|căn cước|cccd",message,re.I):
            message="[Redacted: potential sensitive information]"
        with db(True) as c:
            c.execute("DELETE FROM question_logs WHERE created_at<?",(time.time()-30*86400,))
            c.execute("INSERT INTO question_logs(user_id,question,intent,status,latency_ms,created_at) VALUES (?,?,?,?,?,?)",
              (user["id"],message,result.intent,result.status,latency_ms,time.time()))
    except Exception:log.exception("Question logging unavailable")
def parse_date(value):
    try:
        d=datetime.fromisoformat(value)
        if d.tzinfo is None:raise ValueError()
        return d.timestamp()
    except (ValueError,OverflowError):error(400,"Thời gian cần có múi giờ hợp lệ.")
def bounds(start,end):
    a=parse_date(start);b=parse_date(end)
    if b<a:error(400,"Ngày kết thúc phải sau hoặc bằng ngày bắt đầu.")
    return a,b
def event_access(c,ident,uid):
    e=c.execute("SELECT * FROM events WHERE id=? AND (user_id IS NULL OR user_id=?)",(ident,uid)).fetchone()
    if not e:error(404,"Không tìm thấy sự kiện.")
    return e
def cancel_event_pending(c,event):
    c.execute("UPDATE deliveries SET state='cancelled' WHERE state='pending' AND notice_id IN (SELECT id FROM notices WHERE event_id=? AND kind='reminder')",(event,))
def notice(c,uid,event,kind,key,title):
    now=time.time()
    c.execute("INSERT OR IGNORE INTO notices(user_id,event_id,kind,dedupe_key,title,created_at) VALUES (?,?,?,?,?,?)",(uid,event,kind,key,title,now))
    n=c.execute("SELECT id,created_at FROM notices WHERE dedupe_key=?",(key,)).fetchone()
    if now-n["created_at"]<86400:
        c.execute("""INSERT OR IGNORE INTO deliveries(notice_id,subscription_id,next_attempt)
          SELECT ?,id,? FROM push_subscriptions WHERE user_id=? AND enabled=1""",(n["id"],now,uid))
@router.get("/admin/questions")
def admin_questions(request:Request,start:str|None=None,end:str|None=None,sort:Literal["newest","oldest"]="newest",limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)):
    require_admin(request)
    args=[time.time()-30*86400];clauses=["q.created_at>=?"]
    if start:clauses.append("q.created_at>=?");args.append(parse_date(start))
    if end:clauses.append("q.created_at<?");args.append(parse_date(end))
    where=" AND ".join(clauses);order="DESC" if sort=="newest" else "ASC"
    with db() as c:
        count=c.execute("SELECT COUNT(*) FROM question_logs q WHERE "+where,args).fetchone()[0]
        rows=c.execute("""SELECT q.id,u.username,q.question,q.intent,q.status,q.latency_ms,q.created_at
          FROM question_logs q JOIN users u ON u.id=q.user_id WHERE """+where+
          f" ORDER BY q.created_at {order},q.id {order} LIMIT ? OFFSET ?",[*args,limit,offset]).fetchall()
        by_intent=c.execute("SELECT intent,COUNT(*) AS total FROM question_logs q WHERE "+where+" GROUP BY intent",args).fetchall()
    return {"total":count,"items":[dict(r) for r in rows],"by_intent":[dict(r) for r in by_intent]}
@router.get("/admin/users")
def admin_users(request:Request):
    require_admin(request)
    with db() as c:rows=c.execute("SELECT id,username,role,failed,lock_round,locked_until,hard_locked FROM users ORDER BY username LIMIT 200").fetchall()
    return {"items":[dict(r) for r in rows]}
@router.post("/admin/users/{uid}/unlock")
def admin_unlock(uid:int,request:Request):
    require_admin(request);unlock_account(uid);return {"ok":True}
class EventBody(BaseModel):
    title:StrictStr=Field(min_length=1,max_length=160)
    start:StrictStr=Field(max_length=40)
    end:StrictStr=Field(max_length=40)
    note:StrictStr=Field(default="",max_length=500)
class OfficialEvent(EventBody):
    year:StrictInt=Field(ge=2025,le=2100)
    method:Literal["1a","1b","2"]
    source_url:StrictStr=Field(max_length=500)
    id:StrictStr|None=Field(default=None,max_length=80)
@router.get("/calendar")
def calendar(request:Request,year:int=Query(2026,ge=2025,le=2100),method:Literal["all","1a","1b","2"]="all"):
    user=user_for(request);uid=user["id"] if user else -1
    with db() as c:
        rows=c.execute("""SELECT * FROM events WHERE (user_id IS NULL AND year=? AND (?='all' OR method=?))
           OR user_id=? ORDER BY starts""",(year,method,method,uid)).fetchall()
        reminders=c.execute("SELECT * FROM reminders WHERE user_id=?",(uid,)).fetchall()
        follows=c.execute("SELECT method FROM method_follows WHERE user_id=?",(uid,)).fetchall()
    return {"events":[dict(r) for r in rows],"reminders":[dict(r) for r in reminders],"follows":[r[0] for r in follows]}
@router.post("/calendar/personal")
def add_personal(body:EventBody,request:Request):
    user=require_user(request);start,end=bounds(body.start,body.end);ident=str(uuid.uuid4())
    if not body.title.strip():error(400,"Tên sự kiện không được trống.")
    with db(True) as c:c.execute("INSERT INTO events(id,user_id,title,starts,ends,note) VALUES (?,?,?,?,?,?)",(ident,user["id"],body.title.strip(),start,end,body.note))
    return {"id":ident}
@router.put("/calendar/personal/{ident}")
def edit_personal(ident:str,body:EventBody,request:Request):
    user=require_user(request);start,end=bounds(body.start,body.end)
    if not body.title.strip():error(400,"Tên sự kiện không được trống.")
    with db(True) as c:
        n=c.execute("UPDATE events SET title=?,starts=?,ends=?,note=?,revision=revision+1 WHERE id=? AND user_id=?",(body.title.strip(),start,end,body.note,ident,user["id"])).rowcount
        if not n:error(404,"Không tìm thấy sự kiện cá nhân.")
        cancel_event_pending(c,ident)
    return {"ok":True}
@router.delete("/calendar/personal/{ident}")
def delete_personal(ident:str,request:Request):
    user=require_user(request)
    with db(True) as c:
        if not c.execute("DELETE FROM events WHERE id=? AND user_id=?",(ident,user["id"])).rowcount:error(404,"Không tìm thấy sự kiện cá nhân.")
    return {"ok":True}
@router.post("/admin/calendar")
def upsert_official(body:OfficialEvent,request:Request):
    require_admin(request)
    return save_official(body)
def save_official(body:OfficialEvent):
    if not source_allowed(body.source_url):error(400,"Chọn URL chính thức HCMUS.")
    start,end=bounds(body.start,body.end)
    if not body.title.strip():error(400,"Tên sự kiện không được trống.")
    if datetime.fromtimestamp(start,timezone.utc).year not in (body.year-1,body.year,body.year+1):
        error(400,"Năm sự kiện không phù hợp.")
    with db(True) as c:
        if not c.execute("SELECT 1 FROM monitor_sources WHERE url=?",(body.source_url,)).fetchone():error(400,"Chọn nguồn trong danh sách theo dõi.")
        if body.id:
            old=c.execute("SELECT * FROM events WHERE id=? AND user_id IS NULL",(body.id,)).fetchone()
            if not old:error(404,"Không tìm thấy sự kiện chính thức.")
            ident=body.id
            changed=old["starts"]!=start or old["ends"]!=end or old["method"]!=body.method
            c.execute("UPDATE events SET title=?,starts=?,ends=?,year=?,method=?,source_url=?,note=?,revision=revision+? WHERE id=?",
              (body.title,start,end,body.year,body.method,body.source_url,body.note,int(changed),ident))
            if changed:
                cancel_event_pending(c,ident)
                revision=old["revision"]+1
                ids=c.execute("SELECT user_id FROM method_follows WHERE method IN (?,?) UNION SELECT user_id FROM reminders WHERE event_id=?",(old["method"],body.method,ident)).fetchall()
                for r in ids:notice(c,r[0],ident,"change",f"change:{ident}:{revision}:{r[0]}","Lịch tuyển sinh đã cập nhật: "+body.title)
        else:
            ident="official-"+str(uuid.uuid4())
            c.execute("INSERT INTO events(id,title,starts,ends,year,method,source_url,note) VALUES (?,?,?,?,?,?,?,?)",(ident,body.title,start,end,body.year,body.method,body.source_url,body.note))
            for r in c.execute("SELECT user_id FROM method_follows WHERE method=?",(body.method,)).fetchall():
                notice(c,r[0],ident,"change",f"new:{ident}:{r[0]}","Mốc tuyển sinh mới: "+body.title)
    return {"id":ident}
class ReminderBody(BaseModel):
    event_id:StrictStr=Field(max_length=80)
    before_start:list[StrictInt]=Field(default_factory=list,max_length=4)
    before_end:list[StrictInt]=Field(default_factory=list,max_length=4)
@router.post("/calendar/reminders")
def reminders(body:ReminderBody,request:Request):
    user=require_user(request);uid=user["id"];now=time.time()
    with db(True) as c:
        e=event_access(c,body.event_id,uid)
        for offsets in (body.before_start,body.before_end):
            if any(x not in OFFSETS for x in offsets):error(400,"Chỉ hỗ trợ 0, 1, 4, 7 ngày.")
        wanted={(edge,x) for edge,offsets in (("start",body.before_start),("end",body.before_end)) for x in offsets}
        current={(r["edge"],r["days_before"]):r["id"] for r in c.execute("SELECT id,edge,days_before FROM reminders WHERE user_id=? AND event_id=?",(uid,body.event_id))}
        for pair,ident in current.items():
            if pair not in wanted:
                # Cancel queued deliveries for removed reminder, preserving audit notice.
                c.execute("UPDATE deliveries SET state='cancelled' WHERE state='pending' AND notice_id IN (SELECT id FROM notices WHERE dedupe_key LIKE ?)",(f"reminder:{ident}:%",))
                c.execute("DELETE FROM reminders WHERE id=?",(ident,))
        for edge,x in wanted-current.keys():
            due=e["starts" if edge=="start" else "ends"]-x*86400
            if due<=now:error(400,"Không thể đặt nhắc ở thời điểm đã qua.")
            c.execute("INSERT INTO reminders(user_id,event_id,edge,days_before,created_at) VALUES (?,?,?,?,?)",(uid,body.event_id,edge,x,now))
    return {"ok":True}
class Follow(BaseModel):
    method:Literal["1a","1b","2"]
    enabled:bool
@router.post("/calendar/follow")
def follow(body:Follow,request:Request):
    user=require_user(request)
    with db(True) as c:
        if body.enabled:c.execute("INSERT OR IGNORE INTO method_follows VALUES (?,?)",(user["id"],body.method))
        else:c.execute("DELETE FROM method_follows WHERE user_id=? AND method=?",(user["id"],body.method))
    return {"ok":True}
def push_endpoint_allowed(url):
    try:
        p=urlsplit(url);host=p.hostname or ""
        allowed=("fcm.googleapis.com","updates.push.services.mozilla.com","push.apple.com","push.services.mozilla.com","notify.windows.com")
        return p.scheme=="https" and not p.username and not p.password and p.port in (None,443) and any(host==h or host.endswith("."+h) for h in allowed)
    except ValueError:return False
class PushSub(BaseModel):
    endpoint:StrictStr=Field(max_length=2048)
    keys:dict[str,StrictStr]
@router.get("/push/config")
def push_config():
    key=os.getenv("VAPID_PUBLIC_KEY","")
    return {"enabled":bool(key and os.getenv("VAPID_PRIVATE_KEY") and os.getenv("VAPID_SUBJECT")),"public_key":key}
@router.post("/push/subscribe")
def subscribe(body:PushSub,request:Request):
    user=require_user(request)
    if not push_config()["enabled"]:error(503,"Web Push chưa cấu hình VAPID.")
    if not push_endpoint_allowed(body.endpoint) or set(body.keys)!={"p256dh","auth"} or any(not re.fullmatch(r"[A-Za-z0-9_-]{16,200}={0,2}",v) for v in body.keys.values()):
        error(400,"Push subscription không hợp lệ.")
    payload=json.dumps(body.model_dump())
    with db(True) as c:
        # Reassignment must not carry pending deliveries from a previous account.
        c.execute("DELETE FROM push_subscriptions WHERE endpoint=? AND user_id!=?",(body.endpoint,user["id"]))
        c.execute("""INSERT INTO push_subscriptions(user_id,endpoint,subscription,enabled) VALUES (?,?,?,1)
           ON CONFLICT(endpoint) DO UPDATE SET subscription=excluded.subscription,enabled=1""",(user["id"],body.endpoint,payload))
    return {"ok":True}
class Endpoint(BaseModel):
    endpoint:StrictStr=Field(max_length=2048)
@router.post("/push/unsubscribe")
def unsubscribe(body:Endpoint,request:Request):
    user=require_user(request)
    with db(True) as c:c.execute("DELETE FROM push_subscriptions WHERE user_id=? AND endpoint=?",(user["id"],body.endpoint))
    return {"ok":True}
@router.get("/calendar/notices")
def notices(request:Request):
    user=require_user(request)
    with db() as c:
        rows=c.execute("""SELECT n.id,n.event_id,n.kind,n.title,n.created_at,r.read_at FROM notices n
        LEFT JOIN notice_reads r ON r.notice_id=n.id AND r.user_id=n.user_id WHERE n.user_id=? ORDER BY n.id DESC LIMIT 50""",(user["id"],)).fetchall()
        unread=c.execute("""SELECT COUNT(*) FROM notices n WHERE n.user_id=? AND NOT EXISTS
        (SELECT 1 FROM notice_reads r WHERE r.user_id=n.user_id AND r.notice_id=n.id)""",(user["id"],)).fetchone()[0]
    return {"items":[dict(r) for r in rows],"unread":unread}
@router.post("/calendar/notices/read-all")
def read_all(request:Request):
    uid=require_user(request)["id"]
    with db(True) as c:c.execute("INSERT OR IGNORE INTO notice_reads SELECT user_id,id,? FROM notices WHERE user_id=?",(time.time(),uid))
    return {"ok":True}
@router.post("/calendar/notices/{ident}/read")
def read_notice(ident:int,request:Request):
    uid=require_user(request)["id"]
    with db(True) as c:
        if not c.execute("SELECT 1 FROM notices WHERE id=? AND user_id=?",(ident,uid)).fetchone():error(404,"Không tìm thấy thông báo.")
        c.execute("INSERT OR IGNORE INTO notice_reads VALUES (?,?,?)",(uid,ident,time.time()))
    return {"ok":True}
@router.get("/calendar/event/{ident}")
def calendar_event(ident:str,request:Request):
    user=user_for(request)
    with db() as c:return dict(event_access(c,ident,user["id"] if user else -1))
class ChecklistTask(BaseModel):
    id:StrictStr=Field(min_length=1,max_length=100)
    title:StrictStr=Field(min_length=1,max_length=200)
    done:bool
class ChecklistBody(BaseModel):
    account_id:StrictInt|None=None
    year:StrictInt=Field(ge=2025,le=2100)
    method:StrictStr=Field(pattern=r"^(1a|1b|1c|1d|2|3)$")
    path:StrictStr=Field(default="",max_length=32)
    tasks:list[ChecklistTask]=Field(max_length=80)
@router.put("/calendar/checklist")
def save_checklist(body:ChecklistBody,request:Request):
    uid=require_user(request)["id"]
    if body.account_id is not None and body.account_id!=uid:error(409,"Phiên tài khoản đã thay đổi.")
    if len({t.id for t in body.tasks})!=len(body.tasks):error(400,"Trùng công việc.")
    with db(True) as c:c.execute("""INSERT INTO checklist_progress VALUES (?,?,?,?,?,?)
      ON CONFLICT(user_id,year,method,path) DO UPDATE SET tasks=excluded.tasks,updated_at=excluded.updated_at""",
      (uid,body.year,body.method,body.path,json.dumps([t.model_dump() for t in body.tasks],ensure_ascii=False),time.time()))
    return {"ok":True}
@router.get("/calendar/checklist")
def get_checklist(request:Request,year:int=2026,method:str="all"):
    uid=require_user(request)["id"]
    with db() as c:rows=c.execute("SELECT year,method,path,tasks,updated_at FROM checklist_progress WHERE user_id=? AND year=? AND (?='all' OR method=?) ORDER BY updated_at DESC",(uid,year,method,method)).fetchall()
    return {"items":[{**dict(r),"tasks":json.loads(r["tasks"])} for r in rows]}
@router.get("/admin/monitor/candidates")
def candidates(request:Request):
    require_admin(request)
    with db() as c:rows=c.execute("""SELECT d.*,s.url,s.fetched_at FROM deadline_candidates d JOIN snapshots s ON s.id=d.snapshot_id
      WHERE d.state='pending' ORDER BY d.id DESC LIMIT 100""").fetchall()
    return {"items":[dict(r) for r in rows]}
class CandidateDecision(BaseModel):
    decision:Literal["reviewed","rejected"]
@router.post("/admin/monitor/candidates/{ident}/decision")
def candidate_decision(ident:int,body:CandidateDecision,request:Request):
    uid=require_admin(request)["id"]
    with db(True) as c:
        if not c.execute("UPDATE deadline_candidates SET state=?,reviewed_at=?,reviewed_by=? WHERE id=? AND state='pending'",(body.decision,time.time(),uid,ident)).rowcount:error(409,"Đề xuất đã thay đổi hoặc không còn hiệu lực.")
    return {"ok":True}
def source_allowed(url):
    try:
        p=urlsplit(url)
        return p.scheme=="https" and p.hostname=="tuyensinh.hcmus.edu.vn" and p.port in (None,443) and not p.username and not p.password and not p.query and not p.fragment and p.path.startswith("/") and len(p.path)>1
    except ValueError:return False
class MonitorSource(BaseModel):
    url:StrictStr=Field(max_length=500)
    label:StrictStr=Field(min_length=1,max_length=160)
@router.post("/admin/monitor/sources")
def add_monitor_source(body:MonitorSource,request:Request):
    require_admin(request)
    if not source_allowed(body.url):error(400,"Chỉ chấp nhận HTTPS trên cổng tuyển sinh HCMUS.")
    with db(True) as c:
        if c.execute("SELECT COUNT(*) FROM monitor_sources").fetchone()[0]>=30 and not c.execute("SELECT 1 FROM monitor_sources WHERE url=?",(body.url,)).fetchone():
            error(400,"Đã đạt giới hạn nguồn theo dõi của prototype.")
        c.execute("INSERT OR IGNORE INTO monitor_sources(url,label) VALUES (?,?)",(body.url,body.label.strip()))
    return {"ok":True}
@router.get("/monitor")
def monitor():
    with db() as c:
        sources=c.execute("SELECT url,label,checked_at,successful_at,last_error FROM monitor_sources ORDER BY label").fetchall()
        changes=c.execute("SELECT id,url,summary,detected_at,reviewed_at,review_note FROM changes ORDER BY id DESC LIMIT 30").fetchall()
    return {"sources":[dict(r) for r in sources],"changes":[dict(r) for r in changes]}
class Review(BaseModel):
    note:StrictStr=Field(min_length=1,max_length=500)
@router.post("/admin/monitor/{ident}/review")
def review(ident:int,body:Review,request:Request):
    require_admin(request)
    with db(True) as c:
        if not c.execute("UPDATE changes SET reviewed_at=?,review_note=? WHERE id=?",(time.time(),body.note,ident)).rowcount:error(404,"Không tìm thấy thay đổi.")
    return {"ok":True}
