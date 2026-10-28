"""Bounded, in-memory per-session context for multi-turn HCMUS Guide.

Stores only structured context and the most recent question, not whole transcripts.
This MVP store is local to one FastAPI process and expires after one hour; a DB or
Redis store would be needed for multiple workers / production deployment.
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Callable

from src.assistant.router import detect_intent, extract_year, route
from src.assistant.retrieval import retrieve_majors

YEAR_REQUIRED = frozenset({
    "major_filter", "admission_lookup", "admission_methods",
    "major_exploration", "tuition_lookup",
})
RESET_COMMANDS = frozenset({
    "bat dau lai", "hoi moi", "xoa ngu canh", "quen cau hoi cu",
    "reset", "new chat", "clear chat",
})


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value.lower())
    return "".join(x for x in text if unicodedata.category(x) != "Mn").replace("đ", "d")


def standalone_year(message: str) -> int | None:
    """Accept common short replies, but never treat a full query as 'year only'."""
    simple = _fold(message).strip().strip("?.! ")
    pattern = (
        r"(?:(?:nam|year|chon nam|minh chon nam|cho minh nam|"
        r"la nam|con nam|the con nam|con|the con)\s+)?"
        r"(20\d{2})(?:\s+(?:nhe|nha|a|ah|di|thoi|ban|nha ban))*"
    )
    match = re.fullmatch(pattern, simple)
    return int(match.group(1)) if match else None



# Narrow recognizers for answers to OUR own exploration question.
# These options are editorial search intents, not official program descriptions.
INTEREST_FOCUS = (
    ("ứng dụng", ("xay dung ung dung", "lam ung dung", "lam app",
                  "phat trien ung dung", "viet app", "ung dung",
                  "ky thuat phan mem", "viet phan mem"),
     "phát triển ứng dụng, kỹ thuật phần mềm, công nghệ thông tin",
     "phần mềm ứng dụng công nghệ thông tin kỹ thuật phần mềm"),
    ("thuật toán", ("thuat toan", "giai thuat", "giai bai toan",
                     "lap trinh thuat toan"),
     "thuật toán, khoa học máy tính và toán tin",
     "thuật toán khoa học máy tính toán tin"),
    ("dữ liệu", ("phan tich du lieu", "du lieu", "data", "thong ke",
                "data science", "khoa hoc du lieu"),
     "phân tích dữ liệu, khoa học dữ liệu và thống kê",
     "khoa học dữ liệu thống kê phân tích dữ liệu"),
)


def interest_reply(message: str) -> tuple[str, str, str] | None:
    """Interpret short choices only in an active major-exploration session.

    Reject questions about admissions/other topics and ambiguous multi-choices.
    This never makes claims about a program; it selects retrieval keywords.
    """
    simple = _fold(message).strip().strip("?.! ")
    if len(simple) > 110 or re.search(r"(?<!\d)20\d{2}(?!\d)", simple):
        return None
    if re.search(r"\b(?:a0[0-9]|b00|d0[0-9]|x[0-9]{2})\b", simple):
        return None
    matches = []
    for label, variants, description, search_terms in INTEREST_FOCUS:
        if any(re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", simple)
               for word in variants):
            matches.append((label, description, search_terms))
    return matches[0] if len(matches) == 1 else None




# Academic subject anchors permit open-ended replies without accidentally
# grounding arts/sports hobbies on incidental shared words in profile text.
ACADEMIC_FOCUS = (
    "sinh hoc", "cong nghe sinh hoc", "hoa hoc", "vat ly", "vi mach",
    "ban dan", "moi truong", "dia chat", "hai duong", "hat nhan",
    "y khoa", "toan hoc", "toan tin", "vat lieu", "robot",
    "phan mem", "may tinh", "lap trinh", "thong ke", "du lieu",
    "ky thuat dien tu", "truyen thong", "vien thong",
)


def has_academic_focus(message: str) -> bool:
    simple = _fold(message)
    return any(re.search(r"(?<![a-z0-9])" + re.escape(topic) + r"(?![a-z0-9])", simple)
               for topic in ACADEMIC_FOCUS)



@dataclass(frozen=True)
class Context:
    question: str = ""
    year: int | None = None
    pending_year: bool = False
    awaiting_interest: bool = False
    interest_seed: str = ""
    updated_at: float = 0.0


class ConversationManager:
    def __init__(self, ttl_seconds: int = 3600, max_sessions: int = 500,
                 clock: Callable[[], float] = time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.clock = clock
        self._states: dict[str, Context] = {}
        self._lock = threading.Lock()

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._states.pop(session_id, None)

    def _get(self, session_id: str) -> Context:
        with self._lock:
            now = self.clock()
            # Expire old sessions and bound total memory, without storing chat logs.
            for key, state in list(self._states.items()):
                if now - state.updated_at > self.ttl_seconds:
                    self._states.pop(key, None)
            return self._states.get(session_id, Context())

    def _put(self, session_id: str, state: Context) -> None:
        with self._lock:
            if session_id not in self._states and len(self._states) >= self.max_sessions:
                oldest = min(self._states, key=lambda k: self._states[k].updated_at)
                del self._states[oldest]
            self._states[session_id] = state

    def answer(self, message: str, year: int | None,
               session_id: str | None) -> dict:
        """Route each turn using prior context only from the same session."""
        if session_id is None:
            return route(message, year)  # Backward-compatible stateless clients.

        simple = _fold(message).strip().strip("?.! ")
        if simple in RESET_COMMANDS:
            self.clear(session_id)
            return {
                "answer": "Mình đã bắt đầu một cuộc trò chuyện mới. Bạn muốn hỏi gì về HCMUS?",
                "intent": "unknown", "status": "answered", "sources": [],
            }

        previous = self._get(session_id)
        year_reply = standalone_year(message)
        intent = detect_intent(message)
        original = message
        effective_year = year
        focused = None
        interest_seed = previous.interest_seed

        # The previous AI recommendation specifically asked the student to
        # choose a focus; a short answer is NOT a new unrelated question.
        if previous.awaiting_interest and not previous.pending_year:
            focused = interest_reply(message)
            if (focused is None and intent in ("unknown", "major_exploration")
                and previous.year is not None
                and 3 <= len(message.strip()) <= 110
                and year is None and year_reply is None
                and not re.search(r"(?<!\d)20\d{2}(?!\d)", message)
                and has_academic_focus(message)
                and retrieve_majors(message, previous.year, limit=1)):
                # Also accept free-form short interests supported by SQLite,
                # e.g. 'sinh học' or 'thiết kế vi mạch'. Do not force unrelated
                # replies into a recommendation without retrieval evidence.
                focused = ("sở thích", message.strip(), message.strip())
            if focused is not None:
                _, description, _ = focused
                seed = previous.interest_seed or previous.question
                seed = re.sub(r"(?<!\d)20\d{2}(?!\d)", "", seed)[:220].strip()
                interest_seed = previous.interest_seed or previous.question
                original = (
                    f"Em thích {description}. Trước đó em chia sẻ: {seed}. "
                    f"Hãy gợi ý các ngành dựa trên hướng {description}."
                )
                effective_year = year if year is not None else previous.year
                intent = "major_exploration"

        if focused is not None:
            pass
        elif year_reply is not None and previous.question and (year is None or year == year_reply):
            # 'Ngành nào A01?' -> '2026'    (pending)
            # 'Ngành nào A01 năm 2026?' -> 'còn năm 2027?' (reuse last topic)
            # A follow-up may CHANGE the year from a complete earlier question.
            # Replace its old explicit year to avoid a false year-conflict error.
            original = re.sub(r"(?<!\d)20\d{2}(?!\d)", str(year_reply), previous.question)
            effective_year = year_reply
        elif previous.pending_year and intent == "unknown" and year is None:
            # Non-answer to a pending clarification: don't silently forget it.
            return {
                "answer": "Bạn muốn tra cứu năm nào? Ví dụ: 2026.",
                "intent": detect_intent(previous.question),
                "status": "clarification_needed",
                "sources": [],
            }
        elif year is None and previous.year is not None and intent in YEAR_REQUIRED:
            # In a follow-up, inherit only the missing year, not the whole query.
            # 'Còn B00?' retains year 2026 but replaces the A01 combination.
            # Explicit years in the message ALWAYS take priority.
            embedded_year, problem = extract_year(message, None)
            if not problem and embedded_year is None:
                effective_year = previous.year

        result = route(original, effective_year,
                       focus_query=focused[2] if focused else None)
        detected = detect_intent(original)
        resolved_year, year_problem = extract_year(original, effective_year)

        if year_problem:
            # Do not carry conflicting years forward as a confirmed year.
            return result

        if result["status"] == "clarification_needed" and detected in YEAR_REQUIRED and resolved_year is None:
            self._put(session_id, Context(
                question=original, year=previous.year, pending_year=True,
                interest_seed=interest_seed if focused else "",
                updated_at=self.clock()))
        elif detected in YEAR_REQUIRED and resolved_year is not None:
            exploring = detected == "major_exploration" and result["status"] == "answered"
            self._put(session_id, Context(
                question=original, year=resolved_year, pending_year=False,
                awaiting_interest=exploring,
                interest_seed=(interest_seed or previous.question)[:250]
                    if focused else (original[:250] if exploring else ""),
                updated_at=self.clock()))
        elif intent != "unknown" and not previous.pending_year:
            # Clear stale context when switching to a new independent topic.
            self.clear(session_id)
        return result


conversation_manager = ConversationManager()
