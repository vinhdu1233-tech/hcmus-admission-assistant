"""Local, source-aware lexical retrieval over 2026 HCMUS admissions records.

This is retrieval over verified program names/codes and editorial keyword tags,
not a claim to have ingested full official curriculum descriptions or embeddings.
Requires SQLite only; runs without an AI provider or API key.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter

from src.database.db import all_majors

STOPWORDS = frozenset("""
em toi minh ban hay cho la va voi cua trong neu muon thich nhieu hoc hoc sinh
nganh nao nen chon phu hop nhat co the khong duoc o tai truong hcmus
nam tuyen sinh tu van goi y ve tim hieu chuyen muon theo
""".split())

# Application-authored synonym hints; not official HCMUS descriptions.
SYNONYMS = {
    "code": "lap trinh phan mem",
    "coding": "lap trinh phan mem",
    "python": "lap trinh phan mem",
    "java": "lap trinh phan mem",
    "web": "lap trinh cong nghe thong tin",
    "app": "lap trinh phan mem",
    "game": "lap trinh may tinh",
    "robot": "ky thuat dien tu",
    "robotics": "ky thuat dien tu",
    "du lieu": "thong ke phan tich",
    "data": "du lieu phan tich thong ke",
    "ai": "tri tue nhan tao",
    "vat ly": "dien tu ban dan",
    "hoa hoc": "hoa thi nghiem",
    "sinh hoc": "cong nghe sinh hoc",
    "moi truong": "sinh hoc hoa hoc",
}

def fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    unaccented = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return unaccented.replace("đ", "d")


def tokens(text: str) -> list[str]:
    return [
        term for term in re.findall(r"[a-z0-9]+", fold(text))
        if len(term) > 1 and term not in STOPWORDS and not re.fullmatch(r"20\d\d", term)
    ]


def query_terms(query: str) -> list[str]:
    base = tokens(query)
    expanded = list(base)
    folded = " " + fold(query) + " "
    for phrase, related in SYNONYMS.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", folded):
            expanded.extend(tokens(related))
    return expanded


def retrieve_majors(question: str, year: int, limit: int = 5) -> list[dict]:
    """BM25-like lexical rank on SQLite-backed names and editorial tags.

    Returns an empty list on no evidence, rather than inventing a recommendation.
    Source fields and official identifiers originate in SQLite records.
    """
    terms = query_terms(question)
    if not terms:
        return []
    rows = all_majors(year)
    if not rows:
        return []

    documents = []
    for row in rows:
        tags = json.loads(row["tags_json"])
        # Repetition is intentional: a program name is stronger evidence than
        # editor-generated tags; tags are only hints, not official curriculum.
        document = tokens((row["name"] + " ") * 3 + (" ".join(tags) + " ") * 2)
        documents.append(Counter(document))

    length = [sum(d.values()) or 1 for d in documents]
    avgdl = sum(length) / len(length)
    df = Counter(term for document in documents for term in document)
    query_frequency = Counter(terms)
    n = len(documents)
    ranked = []

    for row, doc, dl in zip(rows, documents, length):
        score = 0.0
        for term, qf in query_frequency.items():
            tf = doc.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * dl / avgdl))
            score *= 1.0  # Keep individual contributions interpretable.
        if score > 0:
            item = dict(row)
            item["tags"] = json.loads(row["tags_json"])
            item["retrieval_score"] = round(score, 4)
            ranked.append(item)

    ranked.sort(key=lambda item: (-item["retrieval_score"], item["name"], item["code"]))
    return ranked[:max(1, min(int(limit), 10))]
