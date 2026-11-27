"""Authenticated chat archive. The browser never chooses another account's context."""
import json,time,uuid,re
from fastapi import Request
from pydantic import BaseModel,StrictStr,Field
from src.product_auth import router,require_user,error
from src.product_db import db

def owned_thread(c,uid,ident):
    row=c.execute("SELECT * FROM chat_threads WHERE id=? AND user_id=?",(ident,uid)).fetchone()
    if not row:error(404,"Không tìm thấy cuộc trò chuyện.")
    return row

def new_thread(c,uid):
    ident=str(uuid.uuid4());now=time.time()
    c.execute("INSERT INTO chat_threads(id,user_id,created_at,updated_at) VALUES (?,?,?,?)",(ident,uid,now,now))
    return ident

@router.get("/chat/threads")
def threads(request:Request):
    uid=require_user(request)["id"]
    with db() as c:rows=c.execute("SELECT id,title,created_at,updated_at FROM chat_threads WHERE user_id=? ORDER BY updated_at DESC LIMIT 100",(uid,)).fetchall()
    return {"items":[dict(r) for r in rows]}

@router.post("/chat/threads")
def create_thread(request:Request):
    uid=require_user(request)["id"]
    with db(True) as c:ident=new_thread(c,uid)
    return {"id":ident}

@router.get("/chat/threads/{ident}")
def thread_detail(ident:str,request:Request):
    uid=require_user(request)["id"]
    with db() as c:
        thread=owned_thread(c,uid,ident)
        rows=c.execute("SELECT question,response,created_at FROM chat_turns WHERE thread_id=? ORDER BY id DESC LIMIT 200",(ident,)).fetchall()
    return {"thread":{"id":thread["id"],"title":thread["title"]},"turns":[{"question":r["question"],"response":json.loads(r["response"]),"created_at":r["created_at"]} for r in reversed(rows)]}

def store_turn(uid,ident,message,result):
    if re.search(r"password|mật khẩu|api\s*key|secret|token|otp|căn cước|cccd",message,re.I):
        message="[Nội dung nhạy cảm đã được ẩn]"
        result={"answer":"[Phản hồi cho nội dung nhạy cảm không được lưu]","intent":result["intent"],"status":result["status"],"sources":[]}
    with db(True) as c:
        owned_thread(c,uid,ident)
        c.execute("INSERT INTO chat_turns(thread_id,question,response,created_at) VALUES (?,?,?,?)",(ident,message,json.dumps(result,ensure_ascii=False),time.time()))
        c.execute("UPDATE chat_threads SET updated_at=?,title=CASE WHEN title='Cuộc trò chuyện mới' THEN ? ELSE title END WHERE id=?",(time.time(),message[:80],ident))
