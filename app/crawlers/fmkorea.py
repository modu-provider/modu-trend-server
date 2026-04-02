from __future__ import annotations

from bs4 import BeautifulSoup

from app.crawlers.common import CrawledItem, fetch_html

# 일부 WAF가 짧은 UA·최소 헤더만내면 430을 반환하는 경우가 있어 브라우저에 가깝게 맞춤
_FM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.fmkorea.com/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Upgrade-Insecure-Requests": "1",
}


def crawl_fmkorea_best2() -> list[CrawledItem]:
    html = fetch_html("https://www.fmkorea.com/best2", extra_headers=_FM_HEADERS)
    soup = BeautifulSoup(html, "html.parser")

    widget = soup.select_one("div.fm_best_widget._bd_pc ul, div.fm_best_widget ul")
    if not widget:
        return []

    items: list[CrawledItem] = []
    for li in widget.select("li.li"):
        title_a = li.select_one("h3.title a[href^='/best2/']")
        if not title_a:
            continue
        title_el = title_a.select_one("span.ellipsis-target")
        title = title_el.get_text(strip=True) if title_el else title_a.get_text(" ", strip=True)

        cat_el = li.select_one("span.category")
        category = cat_el.get_text(" ", strip=True) if cat_el else ""

        items.append(CrawledItem(title=title, category=category))

    return items

