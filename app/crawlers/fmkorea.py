from __future__ import annotations

from bs4 import BeautifulSoup

from app.crawlers.common import CrawledItem, fetch_html


def crawl_fmkorea_best2() -> list[CrawledItem]:
    html = fetch_html("https://www.fmkorea.com/best2")
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

