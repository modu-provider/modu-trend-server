from __future__ import annotations

from bs4 import BeautifulSoup

from app.crawlers.common import CrawledItem, fetch_html

BASE_URL = "https://www.82cook.com"


def crawl_82cook_hot() -> list[CrawledItem]:
    """메인 페이지 '82cook 최근 많이 읽은 글' 목록."""
    html = fetch_html(f"{BASE_URL}/")
    soup = BeautifulSoup(html, "html.parser")

    items: list[CrawledItem] = []
    seen_href: set[str] = set()

    for h2 in soup.find_all("h2"):
        if "많이 읽" not in h2.get_text(strip=True):
            continue
        ul = h2.find_next("ul")
        if not ul:
            continue
        for a in ul.select("li > a[href]"):
            href = (a.get("href") or "").strip()
            if "read.php" not in href or "num=" not in href:
                continue
            if href in seen_href:
                continue
            seen_href.add(href)
            title = a.get_text(" ", strip=True)
            if not title:
                continue
            items.append(CrawledItem(title=title, category=""))
        break

    return items
