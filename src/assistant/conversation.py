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
from src.assistant.dialogue import (Decision, contextual_major_search, decide_rules,
                                    decide_ollama, program_response)

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
    last_codes: tuple[str, ...] = ()
    last_names: tuple[str, ...] = ()
    followup_prompt: str = ""
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
        """Keep only the active question and a bounded shortlist per browser."""
        if session_id is None:
            return route(message, year)  # Stateless legacy API compatibility.

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
        chosen_context: list[dict] | None = None
        selected_focus: str | None = None
        interest_seed = previous.interest_seed

        if year_reply is not None and previous.question and (year is None or year == year_reply):
            # Year-only replies complete a prior query or update an earlier year.
            original = re.sub(r"(?<!\d)20\d{2}(?!\d)", str(year_reply), previous.question)
            effective_year = year_reply
        elif previous.pending_year and intent == "unknown" and year is None:
            return {
                "answer": "Bạn muốn tra cứu năm nào? Ví dụ: 2026.",
                "intent": detect_intent(previous.question),
                "status": "clarification_needed", "sources": [],
            }
        else:
            # The previous recommendation's own follow-up question is part of
            # context. A reply can name ANY academic activity; model-assisted
            # interpretation is optional, while factual grounding is mandatory.
            decision = Decision()
            if previous.last_codes and previous.year is not None:
                decision = decide_rules(
                    message, waiting_for_interest=previous.awaiting_interest,
                    selected_codes=previous.last_codes,
                )
                if (decision.action == "new" and previous.awaiting_interest
                        and intent in ("unknown", "major_exploration")
                        and year is None and len(message) <= 160):
                    decision = decide_ollama(
                        message, question=previous.question,
                        year=previous.year,
                        followup_prompt=previous.followup_prompt,
                        candidate_names=list(previous.last_names),
                    )
            if decision.action in ("detail", "compare"):
                return program_response(
                    year if year is not None else previous.year,
                    previous.last_codes, decision,
                )
            if decision.action == "tuition":
                return route("Học phí của các ngành vừa gợi ý là bao nhiêu?",
                             year if year is not None else previous.year)
            if decision.action == "interest" and previous.awaiting_interest:
                effective_year = year if year is not None else previous.year
                if effective_year != 2026:
                    return route("Em thích " + decision.focus + ", nên học ngành nào?",
                                 effective_year)
                seed = previous.interest_seed or previous.question
                # Supported shortcuts expand editorial retrieval synonyms;
                # open-ended preferences still retain their exact user wording.
                shortcut = interest_reply(message)
                selection = shortcut[2] if shortcut else decision.focus
                chosen_context = contextual_major_search(
                    selection, seed, effective_year, limit=5)
                if not chosen_context:
                    return {
                        "answer": ("Mình hiểu bạn quan tâm đến '" + decision.focus[:90]
                                   + "', nhưng chưa có đủ bằng chứng để chọn ngành "
                                     "từ dữ liệu HCMUS 2026. Bạn muốn tìm hiểu "
                                     "môn học hoặc lĩnh vực cụ thể nào hơn?"),
                        "intent": "major_exploration",
                        "status": "clarification_needed", "sources": [],
                    }
                selected_focus = decision.focus
                original = ("Em muốn tìm hiểu hướng " + decision.focus[:110] +
                            ". Sở thích và bối cảnh trước đó: " +
                            re.sub(r"(?<!\d)20\d{2}(?!\d)", "", seed)[:220] +
                            ". Hãy giới thiệu ngành liên quan bằng thông tin có nguồn.")
                interest_seed = seed
            elif year is None and previous.year is not None and intent in YEAR_REQUIRED:
                # A standalone fresh question inherits the missing year only.
                embedded_year, problem = extract_year(message, None)
                if not problem and embedded_year is None:
                    effective_year = previous.year

        result = route(original, effective_year, focus_query=selected_focus,
                       candidates_override=chosen_context)
        codes = tuple(result.pop("_recommended_codes", ()))
        prompt = result.pop("_followup_prompt", "")
        detected = detect_intent(original)
        resolved_year, year_problem = extract_year(original, effective_year)
        if year_problem:
            return result

        if (result["status"] == "clarification_needed" and
                detected in YEAR_REQUIRED and resolved_year is None):
            self._put(session_id, Context(
                question=original, year=previous.year, pending_year=True,
                updated_at=self.clock(),
            ))
        elif detected in YEAR_REQUIRED and resolved_year is not None:
            exploring = detected == "major_exploration" and result["status"] == "answered"
            self._put(session_id, Context(
                question=original, year=resolved_year,
                awaiting_interest=exploring,
                interest_seed=(interest_seed[:250] if selected_focus else
                               original[:250] if exploring else ""),
                last_codes=codes if exploring else (),
                last_names=tuple(r["name"] for r in chosen_context or [])[:3]
                    if selected_focus else (),
                followup_prompt=prompt, updated_at=self.clock(),
            ))
        elif intent != "unknown" and not previous.pending_year:
            self.clear(session_id)
        return result


conversation_manager = ConversationManager()
