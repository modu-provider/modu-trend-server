from __future__ import annotations

from bs4 import BeautifulSoup

from app.crawlers.common import CrawledItem, fetch_html

POPULAR_URL = "https://www.dogdrip.net/dogdrip?sort_index=popular"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.dogdrip.net/",
}


def crawl_dogdrip_hot() -> list[CrawledItem]:
    """개드립 판 인기글 목록 (`/dogdrip?sort_index=popular`)."""
    html = fetch_html(POPULAR_URL, extra_headers=_HEADERS)
    soup = BeautifulSoup(html, "html.parser")

    items: list[CrawledItem] = []
    seen_srl: set[str] = set()

    for a in soup.select("a.ed.title-link[data-document-srl]"):
        href = (a.get("href") or "").strip()
        if "/dogdrip/" not in href:
            continue
        srl = (a.get("data-document-srl") or "").strip()
        if not srl or srl in seen_srl:
            continue
        seen_srl.add(srl)
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        items.append(CrawledItem(title=title, category=""))

    return items
