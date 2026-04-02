from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class CrawledItem:
    title: str
    category: str


DEFAULT_HEADERS = {
    # 짧은 UA가 일부 사이트에서 더 잘 통과
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def fetch_html(url: str, *, timeout_s: float = 30.0, extra_headers: dict[str, str] | None = None) -> str:
    headers = {**DEFAULT_HEADERS, **(extra_headers or {})}
    with httpx.Client(headers=headers, timeout=timeout_s, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        return r.text

