from __future__ import annotations

from bs4 import BeautifulSoup

from app.crawlers.common import CrawledItem, fetch_html


def crawl_theqoo_hot() -> list[CrawledItem]:
    html = fetch_html("https://theqoo.net/hot")
    soup = BeautifulSoup(html, "html.parser")

    table = soup.select_one("table.theqoo_board_table")
    if not table:
        return []

    items: list[CrawledItem] = []
    for tr in table.select("tbody tr"):
        classes = tr.get("class") or []
        if "notice" in classes or "notice_expand" in classes:
            continue

        cate_td = tr.select_one("td.cate")
        title_td = tr.select_one("td.title")
        if not title_td:
            continue

        title_a = title_td.select_one("a:not(.replyNum)")
        if not title_a:
            continue

        title = title_a.get_text(strip=True)
        category = cate_td.get_text(strip=True) if cate_td else ""
        items.append(CrawledItem(title=title, category=category))

    return items

