"""Product account and verification flow integration tests."""
from test_product import env,client,call,register,login,admin
from src.product_db import db
from src.product_worker import save_snapshot
from src.product_seed import S1

def test_chat_private_archive(env,monkeypatch):
    monkeypatch.setenv("REQUIRE_ACCOUNT_CHAT","1")
    guest=client();a=client();b=client()
    assert guest.post("/chat",json={"message":"Ngành nào xét A01 năm 2026?"}).status_code==401
    register(a,env);register(b,env,"second@example.test","second")
    assert login(a).status_code==200 and login(b,"second").status_code==200
    ident=call(a,"/chat/threads",{}).json()["id"]
    uid=a.get("/product/auth/me").json()["user"]["id"]
    q={"message":"Ngành nào xét A01 năm 2026?","thread_id":ident,"account_id":uid}
    r=a.post("/chat",json=q);assert r.status_code==200,r.text
    path="/product/chat/threads/"+ident
    assert a.get(path).json()["turns"][0]["response"]["answer"]==r.json()["answer"]
    assert b.get("/product/chat/threads").json()["items"]==[]
    assert b.get(path).status_code==404
    assert b.post("/chat",json={**q,"account_id":b.get("/product/auth/me").json()["user"]["id"]}).status_code==404
    assert b.post("/chat",json=q).status_code==409
    assert guest.get(path).status_code==401
    fresh=client();assert login(fresh).status_code==200
    assert fresh.get(path).json()["turns"][0]["question"]==q["message"]
    other=call(a,"/chat/threads",{}).json()["id"]
    assert other!=ident and a.get(path).json()["turns"]
    assert a.get("/product/chat/threads/"+other).json()["turns"]==[]

def test_checklist_latest_account_scope(env):
    a=client();b=client();register(a,env);register(b,env,"second@example.test","second")
    login(a);login(b,"second")
    uid=a.get("/product/auth/me").json()["user"]["id"]
    payload={"account_id":uid,"year":2025,"method":"1a","path":"","tasks":[{"id":"custom-1","title":"TEST","done":True}]}
    assert a.put("/product/calendar/checklist",json=payload).status_code==200
    assert a.get("/product/calendar/checklist?year=0").json()["items"][0]["tasks"][0]["done"] is True
    assert b.get("/product/calendar/checklist?year=0").json()["items"]==[]
    assert b.put("/product/calendar/checklist",json=payload).status_code==409

def test_candidate_atomic_publish_and_history(env):
    a=client();s=client();admin(a);register(s,env);login(s)
    save_snapshot(S1,"Từ 8 giờ ngày 10/12/2026 đến 17 giờ ngày 25/12/2026, nộp hồ sơ phương thức 1a.")
    row=a.get("/product/admin/monitor/candidates").json()["items"][0]
    url="/admin/monitor/candidates/"+str(row["id"])+"/publish"
    payload={"title":"TEST verified","year":2026,"method":"1a","start":"2026-12-10T08:00:00+07:00","end":"2026-12-25T17:00:00+07:00","source_url":S1}
    assert call(s,url,payload).status_code==403
    assert call(a,url,{**payload,"end":"2026-12-01T17:00:00+07:00"}).status_code==400
    assert a.get("/product/admin/monitor/candidates").json()["items"][0]["id"]==row["id"]
    r=call(a,url,payload);assert r.status_code==200,r.text
    assert call(a,url,payload).status_code==409
    assert a.get("/product/admin/monitor/candidates").json()["items"]==[]
    assert a.get("/product/admin/monitor/candidates?history=true").json()["items"][0]["state"]=="reviewed"
    assert any(x["id"]==r.json()["id"] for x in s.get("/product/calendar?year=2026").json()["events"])


def test_publication_inbox_and_targeted_proposals(env):
    a=client();s=client();other=client();admin(a);register(s,env);register(other,env,"other@example.test","other")
    login(s);login(other,"other")
    assert call(s,"/calendar/follow",{"method":"1a","enabled":True}).status_code==200
    payload={"title":"TEST announcement","year":2026,"method":"1a","start":"2026-12-10T08:00:00+07:00","end":"2026-12-25T17:00:00+07:00","source_url":S1}
    result=call(a,"/admin/calendar",payload);assert result.status_code==200,result.text
    assert s.get("/product/calendar/notices").json()["items"][0]["kind"]=="change"
    assert other.get("/product/calendar/notices").json()["items"][0]["kind"]=="announcement"
    assert len(s.get("/product/calendar/proposals").json()["items"])==1
    assert other.get("/product/calendar/proposals").json()["items"]==[]
    assert a.get("/product/admin/overview").json()["students"]==2
    assert other.get("/product/admin/overview").status_code==403
    payload["id"]=result.json()["id"]
    assert call(a,"/admin/calendar",payload).status_code==200
    assert len(other.get("/product/calendar/notices").json()["items"])==1
    payload["end"]="2026-12-30T17:00:00+07:00"
    assert call(a,"/admin/calendar",payload).status_code==200
    assert len(other.get("/product/calendar/notices").json()["items"])==2
    uid=s.get("/product/auth/me").json()["user"]["id"]
    assert other.get("/product/calendar/checklist?year=0&account_id="+str(uid)).status_code==409
