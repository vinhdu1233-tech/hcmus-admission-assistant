"""Run ONE persistent worker alongside the API: periodic source checks and Web Push."""
from __future__ import annotations
import argparse,hashlib,difflib,json,logging,os,time
import httpx
from bs4 import BeautifulSoup
from src.product_db import db
from src.product_seed import SOURCES
from src.product import notice,push_endpoint_allowed,push_config,source_allowed
log=logging.getLogger("hcmus.worker")
def normalized_page(raw):
    soup=BeautifulSoup(raw,"html.parser")
    root=soup.select_one(".entry-content") or soup.select_one("article") or soup.select_one("main")
    if root is None:raise ValueError("No supported content container")
    for element in root.select("script,style,nav,footer,form,aside"):element.decompose()
    text=" ".join(root.stripped_strings)
    # On a listing, include official links to detect newly posted notices too.
    links=sorted(set(a.get("href","") for a in root.select("a[href]") if a.get("href","").startswith("https://tuyensinh.hcmus.edu.vn/")))
    text+="\n"+"\n".join(links)
    if len(text)<80:raise ValueError("Source content unexpectedly short")
    return text[:250000]
def fetch_source(url):
    if not source_allowed(url):raise ValueError("Not allowlisted")
    with db() as c:
        if not c.execute("SELECT 1 FROM monitor_sources WHERE url=?",(url,)).fetchone():raise ValueError("Not registered")
    with httpx.Client(timeout=15,follow_redirects=False,headers={"User-Agent":"HCMUSGuideStudentProject/1.0 (periodic public admissions monitoring)"}) as client:
        with client.stream("GET",url) as response:
            response.raise_for_status()
            chunks=[];size=0
            for chunk in response.iter_bytes():
                size+=len(chunk)
                if size>2_000_000:raise ValueError("Source exceeds limit")
                chunks.append(chunk)
    return normalized_page(b"".join(chunks))
def save_snapshot(url,content,now=None):
    now=time.time() if now is None else now
    digest=hashlib.sha256(content.encode()).hexdigest()
    with db(True) as c:
        last=c.execute("SELECT id,digest,content FROM snapshots WHERE url=? ORDER BY id DESC LIMIT 1",(url,)).fetchone()
        if not last or last["digest"]!=digest:
            ident=c.execute("INSERT INTO snapshots(url,digest,content,fetched_at) VALUES (?,?,?,?)",(url,digest,content,now)).lastrowid
            if last:
                delta=list(difflib.unified_diff(last["content"].split(),content.split(),n=2))
                summary=" ".join(delta[:120])[:1200] or "Source content changed."
                c.execute("INSERT INTO changes(url,previous_id,current_id,summary,detected_at) VALUES (?,?,?,?,?)",(url,last["id"],ident,summary,now))
        c.execute("UPDATE monitor_sources SET checked_at=?,successful_at=?,last_digest=?,last_error=NULL WHERE url=?",(now,now,digest,url))
def poll_sources():
    now=time.time();interval=max(3600,int(os.getenv("MONITOR_INTERVAL_HOURS","24"))*3600)
    with db() as c:due=c.execute("SELECT url FROM monitor_sources WHERE checked_at IS NULL OR checked_at<=?",(now-interval,)).fetchall()
    for row in due:
        url=row["url"]
        try:save_snapshot(url,fetch_source(url))
        except Exception as e:
            log.warning("source check failed: %s (%s)",url,type(e).__name__)
            with db(True) as c:c.execute("UPDATE monitor_sources SET checked_at=?,last_error=? WHERE url=?",(time.time(),type(e).__name__,url))
def queue_reminders(now=None):
    now=time.time() if now is None else now
    with db(True) as c:
        rows=c.execute("""SELECT r.*,e.title,e.starts,e.ends,e.revision FROM reminders r JOIN events e ON e.id=r.event_id
          WHERE (CASE r.edge WHEN 'start' THEN e.starts ELSE e.ends END)-r.days_before*86400 <= ?
          AND (CASE r.edge WHEN 'start' THEN e.starts ELSE e.ends END)-r.days_before*86400 >= r.created_at
          AND (CASE r.edge WHEN 'start' THEN e.starts ELSE e.ends END)-r.days_before*86400 >= ?""",(now,now-86400)).fetchall()
        for r in rows:
            edge="bắt đầu" if r["edge"]=="start" else "kết thúc"
            title=f"{r['title']} — "+(f"còn {r['days_before']} ngày đến mốc {edge}" if r["days_before"] else f"đến mốc {edge}")
            key=f"reminder:{r['id']}:{r['revision']}:{r['user_id']}"
            # Never regenerate an already queued notice/delivery.
            if not c.execute("SELECT 1 FROM notices WHERE dedupe_key=?",(key,)).fetchone():
                notice(c,r["user_id"],r["event_id"],"reminder",key,title)
def send_pending():
    if not push_config()["enabled"]:return
    from pywebpush import webpush,WebPushException
    with db() as c:
        rows=c.execute("""SELECT d.*,n.title,n.created_at,s.subscription,s.endpoint FROM deliveries d
          JOIN notices n ON n.id=d.notice_id JOIN push_subscriptions s ON s.id=d.subscription_id
          WHERE d.state='pending' AND d.next_attempt<=? AND s.enabled=1 AND n.user_id=s.user_id LIMIT 100""",(time.time(),)).fetchall()
    for row in rows:
        state="pending";sent=None;next_attempt=time.time()+min(3600,60*2**row["attempts"])
        try:
            with db() as c:
                fresh=c.execute("SELECT d.state,s.enabled,n.user_id=s.user_id AS owner_ok FROM deliveries d JOIN push_subscriptions s ON s.id=d.subscription_id JOIN notices n ON n.id=d.notice_id WHERE d.notice_id=? AND d.subscription_id=?",(row["notice_id"],row["subscription_id"])).fetchone()
            if not fresh or fresh["state"]!="pending" or not fresh["enabled"] or not fresh["owner_ok"]:continue
            if time.time()-row["created_at"]>86400 or not push_endpoint_allowed(row["endpoint"]):
                state="expired"
            else:
                webpush(subscription_info=json.loads(row["subscription"]),data=json.dumps({"title":"HCMUS Guide","body":row["title"],"url":"/portal.html#calendar"},ensure_ascii=False),
                  vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],vapid_claims={"sub":os.environ["VAPID_SUBJECT"]},ttl=3600,timeout=10)
                state="sent";sent=time.time()
        except Exception as e:
            status=getattr(getattr(e,"response",None),"status_code",None)
            if status in (404,410):
                with db(True) as c:c.execute("DELETE FROM push_subscriptions WHERE id=?",(row["subscription_id"],))
                continue
            if row["attempts"]>=4:state="failed"
            log.warning("push delivery failed (%s)",type(e).__name__)
        with db(True) as c:c.execute("UPDATE deliveries SET state=?,sent_at=?,attempts=attempts+1,next_attempt=? WHERE notice_id=? AND subscription_id=?",(state,sent,next_attempt,row["notice_id"],row["subscription_id"]))
def cleanup():
    with db(True) as c:
        now=time.time()
        c.execute("DELETE FROM question_logs WHERE created_at<?",(now-30*86400,))
        c.execute("DELETE FROM sessions WHERE expires<=?",(now,))
        c.execute("DELETE FROM otps WHERE expires<=?",(now,))
        c.execute("DELETE FROM otp_sends WHERE sent_at<?",(now-3600,))
def main():
    parser=argparse.ArgumentParser();parser.add_argument("--once",action="store_true");parser.add_argument("--skip-monitor",action="store_true");a=parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            cleanup();queue_reminders();send_pending()
            if not a.skip_monitor:poll_sources()
        except Exception:log.exception("worker cycle failed")
        if a.once:return
        time.sleep(30)
if __name__=="__main__":main()
