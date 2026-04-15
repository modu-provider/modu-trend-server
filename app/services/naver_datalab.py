from __future__ import annotations

import calendar
from datetime import date

import httpx

from app.config import settings


def _one_month_ago(d: date) -> date:
    # Subtract one calendar month while keeping day if possible.
    # Example: Mar 31 -> Feb 28/29
    y = d.year
    m = d.month - 1
    if m == 0:
        y -= 1
        m = 12
    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last_day))


def fetch_datalab_search(*, keyword: str) -> dict:
    if not settings.naver_client_id or not settings.naver_client_secret:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET is not set")

    kw = (keyword or "").strip()
    if not kw:
        raise ValueError("keyword is required")

    end = date.today()
    start = _one_month_ago(end)

    payload = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": "date",
        "keywordGroups": [{"groupName": kw, "keywords": [kw]}],
    }

    headers = {
        "X-Naver-Client-Id": settings.naver_client_id,
        "X-Naver-Client-Secret": settings.naver_client_secret,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=20.0) as client:
        r = client.post("https://openapi.naver.com/v1/datalab/search", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()

