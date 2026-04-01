from __future__ import annotations

from bs4 import BeautifulSoup

from app.crawlers.common import CrawledItem, fetch_html


def crawl_instiz_hot() -> list[CrawledItem]:
    html = fetch_html("https://www.instiz.net/")
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one("#boardhot")
    if not container:
        return []

    # rank 중복 제거(탭 섞임 방지)
    seen: set[int] = set()
    deduped: list[CrawledItem] = []
    for a in container.select("div.realchart_item_a a[href]"):
        rank_el = a.select_one("span.rank")
        title_el = a.select_one("span.post_title")
        if not rank_el or not title_el:
            continue
        r = rank_el.get_text(strip=True)
        if not r.isdigit():
            continue
        rn = int(r)
        if not (1 <= rn <= 20) or rn in seen:
            continue
        seen.add(rn)
        category_el = a.select_one("span.minitext")
        category = category_el.get_text(strip=True) if category_el else ""
        title = title_el.get_text(" ", strip=True)
        deduped.append(CrawledItem(title=title, category=category))

    return deduped

