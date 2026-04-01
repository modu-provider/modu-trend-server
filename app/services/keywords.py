from __future__ import annotations

import re
from collections import Counter

# 아주 단순 토큰화(한국어 형태소 분석 없이) 버전
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")

STOPWORDS = {
    # 공통
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "vs",
    # 한국어 자주 등장하는 기능어/잡음
    "오늘",
    "어제",
    "내일",
    "진짜",
    "이거",
    "그거",
    "근황",
    "논란",
    "속보",
    "단독",
    "기자",
    "뉴스",
    "jpg",
    "gif",
    "twt",
    "ㅋㅋ",
    "ㅋㅋㅋ",
    "ㅎㅎ",
    "ㅇㅎ",
}


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(text):
        t = raw.strip().lower()
        if not t:
            continue
        if t in STOPWORDS:
            continue
        if t.isdigit():
            continue
        if len(t) < 2:
            continue
        tokens.append(t)
    return tokens


def top_keywords(texts: list[str], *, limit: int) -> list[tuple[str, int]]:
    c = Counter()
    for t in texts:
        c.update(tokenize(t))
    return c.most_common(limit)

