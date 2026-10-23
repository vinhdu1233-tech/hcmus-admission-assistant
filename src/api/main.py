"""FastAPI API skeleton for the HCMUS Admission & Study Assistant.

This is an integration checkpoint, NOT a real admissions / AI implementation.
M3 will connect router/database and M5 will connect retrieval/LLM.
No admissions data is invented or implied to be verified.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt, StrictStr

app = FastAPI(title="HCMUS Admission & Study Assistant", version="0.1.0")


class ChatRequest(BaseModel):
    message: StrictStr
    admission_year: Annotated[StrictInt, Field(ge=2000, le=2100)] | None = None


class Source(BaseModel):
    title: str
    url: str
    admission_year: int | None = None


class ChatResponse(BaseModel):
    answer: str
    intent: str
    status: Literal["answered", "clarification_needed", "insufficient_evidence", "error"]
    sources: list[Source] = Field(default_factory=list)


def public_error(code: str, detail: str, answer: str) -> dict:
    """Keep all failures compatible with the team's v1 API Contract."""
    return {
        "answer": answer,
        "intent": "unknown",
        "status": "error",
        "sources": [],
        "error": {"code": code, "message": detail},
    }


@app.exception_handler(RequestValidationError)
async def invalid_schema(_: Request, __: RequestValidationError) -> JSONResponse:
    # Never echo raw request content or stack traces into a public response.
    return JSONResponse(
        status_code=422,
        content=public_error(
            "INVALID_SCHEMA",
            "message phải là chuỗi; admission_year phải là số nguyên từ 2000 đến 2100 hoặc null.",
            "Dữ liệu gửi lên không đúng định dạng.",
        ),
    )


def folded(text: str) -> str:
    """Lightweight intent detection for the integration demo only."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    ).replace("đ", "d")


def detect_intent(message: str) -> str:
    text = folded(message)
    if "hoc phi" in text:
        return "tuition_lookup"
    if "a01" in text or "to hop" in text:
        return "major_filter"
    if "phuong thuc" in text:
        return "admission_methods"
    if "nam nhat" in text or "chuan bi" in text:
        return "study_guidance"
    if "lap trinh" in text or "nen chon" in text or "so thich" in text:
        return "major_exploration"
    if "nganh" in text or "tuyen sinh" in text or "diem chuan" in text:
        return "admission_lookup"
    return "unknown"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    message = request.message.strip()
    if not message or len(message) > 1000:
        return JSONResponse(
            status_code=400,
            content=public_error(
                "INVALID_INPUT",
                "Câu hỏi sau khi bỏ khoảng trắng phải có từ 1 đến 1000 ký tự.",
                "Vui lòng nhập một câu hỏi hợp lệ.",
            ),
        )

    intent = detect_intent(message)
    year_matches = {int(x) for x in re.findall(r"(?<!\d)20\d{2}(?!\d)", message)}
    requested_year = request.admission_year

    if len(year_matches) > 1:
        return ChatResponse(
            answer="Bạn muốn tra cứu năm nào? Vui lòng chọn một năm tuyển sinh để mình kiểm tra.",
            intent=intent,
            status="clarification_needed",
            sources=[],
        )
    year_in_text = next(iter(year_matches), None)
    if year_in_text is not None and requested_year is not None and year_in_text != requested_year:
        return ChatResponse(
            answer="Năm trong câu hỏi khác với năm được chọn. Bạn muốn tra cứu năm nào?",
            intent=intent,
            status="clarification_needed",
            sources=[],
        )
    year = requested_year if requested_year is not None else year_in_text

    if re.search(r"api\s*key|password|secret|token|mat khau", folded(message)):
        return ChatResponse(
            answer="Mình không thể chia sẻ mật khẩu, API key hay thông tin cấu hình riêng tư.",
            intent="unknown", status="answered", sources=[],
        )

    if intent in {"tuition_lookup", "major_filter", "admission_methods", "admission_lookup"} and year is None:
        return ChatResponse(
            answer="Bạn muốn tra cứu thông tin tuyển sinh của năm nào?",
            intent=intent,
            status="clarification_needed",
            sources=[],
        )

    if intent == "study_guidance":
        return ChatResponse(
            answer=(
                "Bạn có thể bắt đầu bằng việc ôn kiến thức nền tảng, luyện kỹ năng tự học "
                "và tìm hiểu chương trình đào tạo của ngành mình quan tâm. "
                "Đây là lời khuyên chung, không phải quy định chính thức của HCMUS."
            ),
            intent=intent, status="answered", sources=[],
        )

    # Temporary fallback: there is no real database/AI in this checkpoint.
    # M3/M4/M5 will replace this with verified retrieval and appropriate citations.
    return ChatResponse(
        answer=(
            "Backend FastAPI đã nhận và phân loại câu hỏi của bạn. "
            "Hiện cơ sở dữ liệu tuyển sinh và AI chưa được kết nối; "
            "mình không thể xác minh câu trả lời cụ thể."
        ),
        intent=intent,
        status="insufficient_evidence",
        sources=[],
    )
