"""Verify consent and schedule isolation against real SQLite and API."""
from test_product import env,client,call,register,login,admin,date
from src.product_db import db
from src.product_seed import S1
from src.product_worker import queue_reminders
from datetime import datetime,timezone
def setup_event(a,**extra):
    body={"title":"TEST event","year":datetime.now(timezone.utc).year,"method":"1a","start":date(12),"end":date(14),"source_url":S1,**extra}
    r=call(a,"/admin/calendar",body);assert r.status_code==200,r.text
    body["id"]=r.json()["id"];return body
def rows(c):
    return c.get("/product/calendar/proposals").json()["items"]
def change(a,body,**kwargs):
    body.update(kwargs);r=call(a,"/admin/calendar",body);assert r.status_code==200,r.text
def decision(c,p,value):
    return call(c,f"/calendar/proposals/{p['id']}/decision",{"decision":value})
def plan(c,id):
    return c.get("/product/calendar/event/"+id).json()["personal_plan"]
def test_new_followed_event_requires_acceptance(env):
    a=client();s=client();admin(a);register(s,env);login(s)
    assert call(s,"/calendar/follow",{"method":"1a","enabled":True}).status_code==200
    e=setup_event(a);p=rows(s)[0]
    assert p["old_starts"] is None and plan(s,e["id"]) is None
    reminder={"event_id":e["id"],"before_start":[4],"before_end":[7]}
    assert call(s,"/calendar/reminders",reminder).status_code==409
    assert decision(s,p,"deferred").status_code==200
    assert plan(s,e["id"]) is None
    assert decision(s,p,"accepted").status_code==200
    assert plan(s,e["id"])["revision"]==1
    assert call(s,"/calendar/reminders",reminder).status_code==200
    assert [h["decision"] for h in rows(s)[0]["history"]]==["deferred","accepted"]
    assert decision(s,p,"accepted").status_code==200
    assert len(rows(s)[0]["history"])==2
def test_user_decisions_are_independent_and_dates_stay_pinned(env):
    a=client();s=client();b=client();admin(a);register(s,env);register(b,env,"other@example.test","other");login(s);login(b,"other")
    e=setup_event(a)
    for c in (s,b):assert call(c,"/calendar/reminders",{"event_id":e["id"],"before_start":[4],"before_end":[7]}).status_code==200
    old=plan(s,e["id"])
    change(a,e,start=date(16),end=date(19))
    assert s.get("/product/calendar/event/"+e["id"]).json()["revision"]==2
    assert plan(s,e["id"])["starts"]==old["starts"]
    assert plan(b,e["id"])["ends"]==old["ends"]
    sp,bp=rows(s)[0],rows(b)[0]
    assert decision(b,sp,"accepted").status_code==404
    assert decision(s,sp,"accepted").status_code==200
    assert decision(b,bp,"rejected").status_code==200
    assert plan(s,e["id"])["revision"]==2 and plan(b,e["id"])["revision"]==1
    assert decision(b,bp,"accepted").status_code==409
    for c in (s,b):
        rr=c.get("/product/calendar").json()["reminders"]
        assert {(r["edge"],r["days_before"]) for r in rr if r["event_id"]==e["id"]}=={("start",4),("end",7)}
def test_superseded_proposal_cannot_overwrite_current_revision(env):
    a=client();s=client();admin(a);register(s,env);login(s)
    e=setup_event(a)
    assert call(s,"/calendar/reminders",{"event_id":e["id"],"before_end":[4]}).status_code==200
    old=plan(s,e["id"])
    change(a,e,end=date(16));p=rows(s)[0]
    assert decision(s,p,"deferred").status_code==200
    change(a,e,end=date(18));latest=rows(s)[0]
    assert latest["revision"]==3 and latest["old_ends"]==old["ends"]
    assert decision(s,p,"accepted").status_code==409
    assert decision(s,latest,"accepted").status_code==200
    assert plan(s,e["id"])["revision"]==3
    assert next(x for x in rows(s) if x["id"]==p["id"])["state"]=="superseded"
def test_scheduler_keeps_old_reminder_until_consent(env):
    a=client();s=client();admin(a);register(s,env);login(s)
    e=setup_event(a)
    assert call(s,"/calendar/reminders",{"event_id":e["id"],"before_end":[7]}).status_code==200
    old=plan(s,e["id"])
    change(a,e,end=date(21));p=rows(s)[0]
    due=old["ends"]-7*86400+1
    queue_reminders(due);queue_reminders(due+1)
    notices=[n for n in s.get("/product/calendar/notices").json()["items"] if n["kind"]=="reminder"]
    assert len(notices)==1 and "Lịch cá nhân cũ" in notices[0]["title"]
    assert decision(s,p,"accepted").status_code==200
    new=plan(s,e["id"]);due=new["ends"]-7*86400+1
    queue_reminders(due);queue_reminders(due+1)
    notices=[n for n in s.get("/product/calendar/notices").json()["items"] if n["kind"]=="reminder"]
    assert len(notices)==2 and "Lịch cá nhân cũ" not in notices[0]["title"]
def test_migrates_old_reminders_on_first_change(env):
    a=client();s=client();admin(a);register(s,env);login(s)
    e=setup_event(a)
    assert call(s,"/calendar/reminders",{"event_id":e["id"],"before_end":[4]}).status_code==200
    old=plan(s,e["id"])
    with db(True) as c:c.execute("DELETE FROM personal_event_plans")
    change(a,e,end=date(20))
    assert plan(s,e["id"])["ends"]==old["ends"] and rows(s)[0]["old_revision"]==1
