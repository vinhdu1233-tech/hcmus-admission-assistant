"""FastAPI + SQLite router integration for HCMUS Guide MVP.
Major exploration uses verified retrieval and optional AI explanations.
"""
from __future__ import annotations
from typing import Annotated, Literal
from uuid import UUID
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt, StrictStr
from src.assistant.conversation import conversation_manager
from src.database.db import ensure_database

app=FastAPI(title='HCMUS Admission & Study Assistant',version='0.2.0')

class ChatRequest(BaseModel):
    message: StrictStr
    admission_year: Annotated[StrictInt,Field(ge=2000,le=2100)] | None = None
    conversation_id: UUID | None = None
class Source(BaseModel):
    title:str
    url:str
    admission_year:int|None=None
class ChatResponse(BaseModel):
    answer:str
    intent:str
    status:Literal['answered','clarification_needed','insufficient_evidence','error']
    sources:list[Source]=Field(default_factory=list)

def public_error(code:str,detail:str,answer:str)->dict:
    return {'answer':answer,'intent':'unknown','status':'error','sources':[],
            'error':{'code':code,'message':detail}}

@app.exception_handler(RequestValidationError)
async def invalid_schema(_:Request,__:RequestValidationError):
    return JSONResponse(status_code=422,content=public_error('INVALID_SCHEMA',
       'message phải là chuỗi; admission_year phải là số nguyên từ 2000 đến 2100 hoặc null.',
       'Dữ liệu gửi lên không đúng định dạng.'))

@app.get('/health')
def health():
    return {'status':'ok'}

@app.post('/chat',response_model=ChatResponse)
def chat(request:ChatRequest):
    msg=request.message.strip()
    if not msg or len(msg)>1000:
        return JSONResponse(status_code=400,content=public_error('INVALID_INPUT',
            'Câu hỏi sau khi bỏ khoảng trắng phải có từ 1 đến 1000 ký tự.',
            'Vui lòng nhập một câu hỏi hợp lệ.'))
    try:
        ensure_database()
        return ChatResponse(**conversation_manager.answer(
            msg, request.admission_year,
            str(request.conversation_id) if request.conversation_id is not None else None
        ))
    except Exception:
        # Avoid exposing internal details and secrets to end users.
        return JSONResponse(status_code=503,content=public_error('SERVICE_UNAVAILABLE',
            'Database chưa sẵn sàng.','Hệ thống tạm thời không truy xuất được cơ sở dữ liệu.'))
