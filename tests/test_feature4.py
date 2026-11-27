"""F4 acceptance scenarios, using actual FastAPI/SQLite and controlled source fixtures."""
import time
from datetime import datetime,timezone,timedelta
from test_product import env,client,call,register,login,admin,date,event
from src.product_db import db
from src.product_seed import S1
from src.product_worker import save_snapshot,queue_reminders
from src.deadline_extraction import extract
def test_f4_explicit_range_and_qualification():
    text="Từ 11 giờ 00 ngày 01/6/2026 đến 17 giờ ngày 20/6/2026, thí sinh nộp hồ sơ phương thức 1a."
    rows=extract(text)
    assert len(rows)==1 and rows[0]["year"]==2026 and rows[0]["method"]=="1a"
    assert datetime.fromtimestamp(rows[0]["ends"],timezone.utc).hour==10
    assert "hồ sơ" in rows[0]["evidence"]
def test_f4_reject_missing_year_invalid_and_ambiguous():
    for text in ("Từ ngày 01/6 đến ngày 20/6 nộp hồ sơ phương thức 1a.",
                 "Từ ngày 31/2/2026 đến ngày 20/6/2026 nộp hồ sơ phương thức 1a.",
                 "Từ ngày 21/6/2026 đến ngày 20/6/2026 nộp hồ sơ phương thức 1a.",
                 "Từ ngày 01/6/2026 đến ngày 20/6/2026 nộp hồ sơ phương thức 1a và phương thức 2."):
        assert extract(text)==[]
def test_f4_extension_keeps_unknown_start():
    r=extract("Gia hạn nộp hồ sơ phương thức 1a đến 17 giờ ngày 25/6/2026.")
    assert len(r)==1 and r[0]["starts"] is None
def test_f4_candidate_admin_only_and_not_published(env):
    a=client();s=client();admin(a);register(s,env);login(s)
    before=s.get("/product/calendar?year=2027").json()["events"]
    save_snapshot(S1,"Từ ngày 01/6/2027 đến ngày 20/6/2027 nộp hồ sơ phương thức 1a.")
    rows=a.get("/product/admin/monitor/candidates").json()["items"]
    assert len(rows)==1 and rows[0]["year"]==2027
    assert s.get("/product/admin/monitor/candidates").status_code==403
    assert s.get("/product/calendar?year=2027").json()["events"]==before
    assert call(a,f"/admin/monitor/candidates/{rows[0]['id']}/decision",{"decision":"rejected"}).status_code==200
    assert a.get("/product/admin/monitor/candidates").json()["items"]==[]
def test_f4_stale_proposals_and_dedup(env):
    a=client();admin(a)
    text="Từ ngày 01/6/2027 đến ngày 20/6/2027 nộp hồ sơ phương thức 1a."
    save_snapshot(S1,text);save_snapshot(S1,text)
    old=a.get("/product/admin/monitor/candidates").json()["items"][0]["id"]
    save_snapshot(S1,text.replace("20/6","25/6"))
    rows=a.get("/product/admin/monitor/candidates").json()["items"]
    assert len(rows)==1 and rows[0]["id"]!=old
    assert call(a,f"/admin/monitor/candidates/{old}/decision",{"decision":"reviewed"}).status_code==409
def test_f4_discovery_only_official_articles(env):
    url="https://tuyensinh.hcmus.edu.vn/danh-muc/thong-tin-tuyen-sinh/"
    save_snapshot(url,"https://tuyensinh.hcmus.edu.vn/2027-thong-bao-moi/\nhttps://evil.example/2027-thong-bao-moi/")
    with db() as c:
        urls={x[0] for x in c.execute("SELECT url FROM monitor_sources")}
    assert "https://tuyensinh.hcmus.edu.vn/2027-thong-bao-moi/" in urls
    assert not any("evil" in x for x in urls)
def test_f4_checklist_isolation_and_validation(env):
    s=client();b=client();register(s,env);register(b,env,"other@example.test","other");login(s);login(b,"other")
    uid=s.get("/product/auth/me").json()["user"]["id"]
    body={"account_id":uid,"year":2026,"method":"1a","path":"","tasks":[{"id":"a","title":"Hồ sơ","done":False}]}
    assert s.put("/product/calendar/checklist",json=body).status_code==200
    assert b.put("/product/calendar/checklist",json=body).status_code==409
    assert b.get("/product/calendar/checklist").json()["items"]==[]
    assert s.get("/product/calendar/checklist").json()["items"][0]["tasks"][0]["done"] is False
def test_f4_linked_progress_in_reminder(env):
    a=client();s=client();admin(a);register(s,env);login(s)
    y=datetime.now(timezone.utc).year
    r=call(a,"/admin/calendar",{"title":"Future test","year":y,"method":"1a","start":date(9),"end":date(10),"source_url":S1})
    i=r.json()["id"]
    assert s.put("/product/calendar/checklist",json={"year":y,"method":"1a","tasks":[{"id":"a","title":"A","done":True},{"id":"b","title":"B","done":False}]}).status_code==200
    assert call(s,"/calendar/reminders",{"event_id":i,"before_start":[7]}).status_code==200
    with db() as c:t=c.execute("SELECT starts FROM events WHERE id=?",(i,)).fetchone()[0]
    queue_reminders(t-7*86400+1);queue_reminders(t-7*86400+2)
    rows=s.get("/product/calendar/notices").json()["items"]
    reminders=[n for n in rows if n["kind"]=="reminder"]
    announcements=[n for n in rows if n["kind"]=="announcement"]
    assert len(reminders)==1 and "Checklist còn 1 việc" in reminders[0]["title"]
    assert len(announcements)==1 and announcements[0]["event_id"]==i
def test_f4_inbox_read_and_deep_link_isolation(env):
    s=client();b=client();register(s,env);register(b,env,"other@example.test","other");login(s);login(b,"other")
    i=event(s,days=2)
    assert call(s,"/calendar/reminders",{"event_id":i,"before_start":[1]}).status_code==200
    with db() as c:t=c.execute("SELECT starts FROM events WHERE id=?",(i,)).fetchone()[0]
    queue_reminders(t-86400+1)
    d=s.get("/product/calendar/notices").json();n=d["items"][0]["id"]
    assert d["unread"]==1 and d["items"][0]["event_id"]==i
    assert b.get("/product/calendar/event/"+i).status_code==404
    assert call(b,f"/calendar/notices/{n}/read",{}).status_code==404
    assert s.get("/product/calendar/event/"+i).status_code==200
    assert call(s,f"/calendar/notices/{n}/read",{}).status_code==200
    assert s.get("/product/calendar/notices").json()["unread"]==0
    assert call(s,"/calendar/notices/read-all",{}).status_code==200
def test_f4_historical_data_scope(env):
    g=client()
    r=g.get("/product/calendar?year=2026&method=2").json()["events"]
    assert any("lệ phí" in e["title"] for e in r) and any("nhập học" in e["title"] for e in r)
    assert all(e["year"]==2026 and e["method"]=="2" for e in r)
    assert g.get("/product/calendar?year=2027").json()["events"]==[]
