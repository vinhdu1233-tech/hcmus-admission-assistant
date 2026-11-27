"""Integration tests for the actual product APIs, persistent SQLite and worker logic."""
from __future__ import annotations
import json,time,os
from datetime import datetime,timezone,timedelta
import pytest,bcrypt
from fastapi.testclient import TestClient
from src.api.main import app
from src.product_db import db
from src import product_auth as auth
from src.product import push_endpoint_allowed
from src.product_worker import save_snapshot,queue_reminders,normalized_page,send_pending
from src.product_seed import S1
PW="GoodPass7!"
PW2="NewPass8!"
@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setenv("HCMUS_PRODUCT_DB_PATH",str(tmp_path/"product.sqlite3"))
    monkeypatch.setenv("HCMUS_DB_PATH",str(tmp_path/"admissions.sqlite3"))
    monkeypatch.setenv("HCMUS_OTP_SECRET","only-for-tests-"+"x"*40)
    monkeypatch.setenv("AI_PROVIDER","none")
    monkeypatch.setenv("COOKIE_SECURE","0")
    mail={}
    monkeypatch.setattr(auth,"send_otp",lambda email,code,purpose:mail.__setitem__((email,purpose),code))
    return mail
def client():return TestClient(app)
def call(c,path,body):return c.post("/product"+path,json=body)
def register(c,mail,email="student@example.test",name="student",pw=PW):
    assert call(c,"/auth/register/code",{"email":email}).status_code==200
    code=mail[(email,"register")]
    assert call(c,"/auth/register",{"email":email,"username":name,"password":pw,"code":code}).status_code==200
def login(c,name="student",pw=PW):
    return call(c,"/auth/login",{"identifier":name,"password":pw})
def admin(c):
    auth.create_admin("admin@example.test","admin",PW)
    assert login(c,"admin").status_code==200
def date(offset):
    return (datetime.now(timezone.utc)+timedelta(days=offset)).isoformat()
def event(c,title="My private date",days=10):
    r=call(c,"/calendar/personal",{"title":title,"start":date(days),"end":date(days+2)})
    assert r.status_code==200,r.text
    return r.json()["id"]
def get_events(c):
    return c.get("/product/calendar?year=2026&method=all").json()["events"]

def test_otp_registration_hash_and_replay(env):
    c=client()
    assert call(c,"/auth/register/code",{"email":"student@example.test"}).status_code==200
    code=env[("student@example.test","register")]
    with db() as d:row=d.execute("SELECT * FROM otps").fetchone();assert row["digest"]!=code
    assert call(c,"/auth/register/code",{"email":"student@example.test"}).status_code==429
    payload={"email":"student@example.test","username":"student","password":PW,"code":"000000" if code!="000000" else "111111"}
    assert call(c,"/auth/register",payload).status_code==400
    payload["code"]=code;assert call(c,"/auth/register",payload).status_code==200
    assert call(c,"/auth/register",payload).status_code==400
    with db() as d:
        u=d.execute("SELECT * FROM users").fetchone()
        assert u["role"]=="student" and u["password_hash"]!=PW
        assert bcrypt.checkpw(PW.encode(),u["password_hash"].encode())
def test_weak_password_rejected(env):
    c=client();call(c,"/auth/register/code",{"email":"student@example.test"})
    for pw in ("abc1!","abcdef1!","Abcdefgh!","Abcdefg1","Abc 123!"):
        r=call(c,"/auth/register",{"email":"student@example.test","username":"student","password":pw,"code":env[("student@example.test","register")]})
        assert r.status_code==400
def test_expired_otp_and_attempt_limit(env):
    c=client();call(c,"/auth/register/code",{"email":"student@example.test"})
    code=env[("student@example.test","register")]
    with db(True) as d:d.execute("UPDATE otps SET expires=?",(time.time()-1,))
    p={"email":"student@example.test","username":"student","password":PW,"code":code}
    assert call(c,"/auth/register",p).status_code==400
    with db(True) as d:d.execute("UPDATE otps SET expires=?,attempts=5",(time.time()+600,))
    assert call(c,"/auth/register",p).status_code==400
def test_two_stage_lock_and_admin_only_unlock(env):
    a=client();s=client();admin(a);register(s,env)
    assert login(s).status_code==200
    for n in range(4):assert login(s,pw="Wrong7!").status_code==(423 if n==3 else 401)
    assert s.get("/product/auth/me").json()["user"] is None
    assert login(s).status_code==423
    with db(True) as d:
        u=d.execute("SELECT * FROM users WHERE username='student'").fetchone()
        assert 890<u["locked_until"]-time.time()<=900 and u["lock_round"]==1
        uid=u["id"]
        d.execute("UPDATE users SET locked_until=? WHERE id=?",(time.time()-1,uid))
    for n in range(4):assert login(s,pw="Wrong7!").status_code==(423 if n==3 else 401)
    with db() as d:assert d.execute("SELECT hard_locked FROM users WHERE id=?",(uid,)).fetchone()[0]==1
    assert login(s).status_code==423
    assert call(s,f"/admin/users/{uid}/unlock",{}).status_code==401
    assert call(a,f"/admin/users/{uid}/unlock",{}).status_code==200
    assert login(s).status_code==200
    assert call(s,f"/admin/users/{uid}/unlock",{}).status_code==403
def test_password_reset_revokes_sessions_but_not_lock(env):
    s=client();register(s,env);assert login(s).status_code==200
    with db(True) as d:d.execute("DELETE FROM otp_sends")
    assert call(s,"/auth/reset/code",{"email":"student@example.test"}).status_code==200
    assert call(s,"/auth/reset",{"email":"student@example.test","password":PW2,"code":env[("student@example.test","reset")]}).status_code==200
    assert s.get("/product/auth/me").json()["user"] is None
    assert login(s,pw=PW).status_code==401
    assert login(s,pw=PW2).status_code==200
    with db(True) as d:
        d.execute("UPDATE users SET hard_locked=1 WHERE username='student'");d.execute("DELETE FROM otp_sends")
    call(s,"/auth/reset/code",{"email":"student@example.test"})
    assert call(s,"/auth/reset",{"email":"student@example.test","password":PW,"code":env[("student@example.test","reset")]}).status_code==200
    assert login(s,pw=PW).status_code==423
def test_roles_and_question_logs(env):
    a=client();s=client();g=client();admin(a);register(s,env);assert login(s).status_code==200
    assert g.get("/product/admin/questions").status_code==401
    assert s.get("/product/admin/questions").status_code==403
    assert s.post("/chat",json={"message":"Ngành nào xét A01 năm 2026?"}).status_code==200
    assert s.post("/chat",json={"message":"Các phương thức tuyển sinh năm 2026?"}).status_code==200
    assert g.post("/chat",json={"message":"Ngành nào xét B00 năm 2026?"}).status_code==200
    rows=a.get("/product/admin/questions?sort=oldest").json()["items"]
    assert len(rows)==2 and rows[0]["username"]=="student" and "A01" in rows[0]["question"]
    assert a.get("/product/admin/questions?sort=newest").json()["items"][0]["id"]==rows[1]["id"]
    assert a.get("/product/admin/questions",params={"start":date(1)}).json()["total"]==0
def test_login_cookie_and_logout(env):
    s=client();register(s,env)
    r=login(s);assert r.status_code==200
    assert "HttpOnly" in r.headers["set-cookie"] and "SameSite=strict" in r.headers["set-cookie"]
    with db() as d:assert d.execute("SELECT token_hash FROM sessions").fetchone()[0]!=s.cookies.get(auth.COOKIE)
    assert call(s,"/auth/logout",{}).status_code==200
    assert s.get("/product/auth/me").json()["user"] is None
def test_calendar_filters_historical_and_ownership(env):
    a=client();b=client();g=client();register(a,env,"a@example.test","aaa");register(b,env,"b@example.test","bbb")
    assert login(a,"aaa").status_code==200;assert login(b,"bbb").status_code==200
    rows=g.get("/product/calendar?year=2026&method=1a").json()["events"]
    assert len(rows)==1 and rows[0]["method"]=="1a" and rows[0]["source_url"]==S1
    assert not g.get("/product/calendar?year=2027&method=all").json()["events"]
    i=event(a);assert any(e["id"]==i for e in get_events(a))
    assert all(e["id"]!=i for e in get_events(b)+get_events(g))
    assert b.delete("/product/calendar/personal/"+i).status_code==404
    assert call(b,"/calendar/reminders",{"event_id":i,"before_start":[4]}).status_code==404
    assert a.delete("/product/calendar/personal/"+i).status_code==200
def test_invalid_event_and_past_reminders(env):
    s=client();register(s,env);login(s)
    assert call(s,"/calendar/personal",{"title":"Bad","start":date(5),"end":date(1)}).status_code==400
    i=event(s,days=-10)
    assert call(s,"/calendar/reminders",{"event_id":i,"before_start":[0]}).status_code==400
def test_reminder_both_edges_idempotent_and_reschedule(env):
    s=client();register(s,env);login(s);i=event(s,days=10)
    data={"event_id":i,"before_start":[7,4,0],"before_end":[7,4,0]}
    assert call(s,"/calendar/reminders",data).status_code==200
    assert call(s,"/calendar/reminders",data).status_code==200
    with db() as d:
        r=d.execute("SELECT * FROM events WHERE id=?",(i,)).fetchone()
        due=r["starts"]-7*86400
        assert d.execute("SELECT COUNT(*) FROM reminders WHERE event_id=?",(i,)).fetchone()[0]==6
    queue_reminders(due+1);queue_reminders(due+2)
    with db() as d:assert d.execute("SELECT COUNT(*) FROM notices").fetchone()[0]==1
    assert s.put("/product/calendar/personal/"+i,json={"title":"New time","start":date(15),"end":date(17)}).status_code==200
    with db() as d:
        e=d.execute("SELECT * FROM events WHERE id=?",(i,)).fetchone();assert e["revision"]==2
    queue_reminders(e["starts"]-7*86400+1)
    with db() as d:assert d.execute("SELECT COUNT(*) FROM notices").fetchone()[0]==2
def test_monitor_diff_no_duplicate_and_admin_review(env):
    a=client();admin(a)
    raw=b"<article><p>"+b"Admission information "*10+b"20 June</p><script>ignored</script></article>"
    x=normalized_page(raw);assert "ignored" not in x
    save_snapshot(S1,x);save_snapshot(S1,x);save_snapshot(S1,x.replace("20 June","25 June"));save_snapshot(S1,x.replace("20 June","25 June"))
    d=a.get("/product/monitor").json();assert len(d["changes"])==1
    change=d["changes"][0];assert change["reviewed_at"] is None and "25" in change["summary"]
    assert call(a,f"/admin/monitor/{change['id']}/review",{"note":"Checked official source"}).status_code==200
    assert a.get("/product/monitor").json()["changes"][0]["reviewed_at"]
    assert any(e["id"]=="official-2026-1a-application" for e in get_events(a))
def test_official_update_alert_and_new_source(env):
    a=client();s=client();admin(a);register(s,env);login(s)
    assert call(s,"/calendar/follow",{"method":"1a","enabled":True}).status_code==200
    url="https://tuyensinh.hcmus.edu.vn/new-notice/"
    assert call(a,"/admin/monitor/sources",{"url":"http://127.0.0.1/","label":"bad"}).status_code==400
    assert call(s,"/admin/monitor/sources",{"url":url,"label":"Official"}).status_code==403
    assert call(a,"/admin/monitor/sources",{"url":url,"label":"Official"}).status_code==200
    y=datetime.now(timezone.utc).year
    p={"title":"Verified new period","year":y,"method":"1a","start":date(10),"end":date(12),"source_url":url}
    r=call(a,"/admin/calendar",p);assert r.status_code==200,r.text
    p["id"]=r.json()["id"];p["end"]=date(14)
    assert call(a,"/admin/calendar",p).status_code==200
    assert len(s.get("/product/calendar/notices").json()["items"])==2
    assert call(s,"/admin/calendar",p).status_code==403
def test_push_rejects_ssrf_and_queue_delivery(env,monkeypatch):
    s=client();register(s,env);login(s)
    for bad in ("http://fcm.googleapis.com/x","https://127.0.0.1/x","https://fcm.googleapis.com.evil.test/x","https://fcm.googleapis.com:444/x"):
        assert not push_endpoint_allowed(bad)
    monkeypatch.setenv("VAPID_PUBLIC_KEY","public-test-key")
    monkeypatch.setenv("VAPID_PRIVATE_KEY","private-test-key")
    monkeypatch.setenv("VAPID_SUBJECT","mailto:test@example.test")
    payload={"endpoint":"https://fcm.googleapis.com/fcm/send/test","keys":{"p256dh":"a"*87,"auth":"b"*22}}
    assert call(s,"/push/subscribe",payload).status_code==200
    i=event(s,days=1)
    assert call(s,"/calendar/reminders",{"event_id":i,"before_start":[0]}).status_code==200
    with db() as d:e=d.execute("SELECT * FROM events WHERE id=?",(i,)).fetchone()
    queue_reminders(e["starts"]+1)
    sent=[]
    import pywebpush
    monkeypatch.setattr(pywebpush,"webpush",lambda **kw:sent.append(kw))
    send_pending();send_pending()
    assert len(sent)==1 and json.loads(sent[0]["data"])["title"]=="HCMUS Guide"
    with db() as d:assert d.execute("SELECT state FROM deliveries").fetchone()[0]=="sent"
    assert call(s,"/push/unsubscribe",{"endpoint":payload["endpoint"]}).status_code==200
