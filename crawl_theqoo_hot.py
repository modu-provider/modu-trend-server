"""
테스트용: 더쿠 핫 게시판 목록을 가져와 콘솔에 출력합니다.

의존성: pip install beautifulsoup4
"""

from __future__ import annotations

import sys
from urllib.request import Request, urlopen

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except OSError:
        pass

from bs4 import BeautifulSoup

HOT_URL = "https://theqoo.net/hot"
BASE = "https://theqoo.net"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def fetch_html(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_posts(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.theqoo_board_table")
    if not table:
        return []

    rows: list[dict[str, str]] = []
    for tr in table.select("tbody tr"):
        classes = tr.get("class") or []
        if "notice" in classes or "notice_expand" in classes:
            continue

        cate_td = tr.select_one("td.cate")
        title_td = tr.select_one("td.title")

        if not title_td:
            continue

        title_a = title_td.select_one("a:not(.replyNum)")
        if not title_a or not title_a.get("href"):
            continue

        title = title_a.get_text(strip=True)
        category = cate_td.get_text(strip=True) if cate_td else ""

        rows.append(
            {
                "title": title,
                "category": category,
            }
        )
    return rows


def main() -> None:
    print(f"요청: {HOT_URL}\n")
    html = fetch_html(HOT_URL)
    posts = parse_posts(html)
    if not posts:
        print("목록을 찾지 못했습니다. (HTML 구조 변경 또는 차단 여부를 확인하세요.)")
        return

    for i, p in enumerate(posts, start=1):
        print(f"[{i:02d}] {p['title']}")
        if p["category"]:
            print(f"     {p['category']}")
        print()


if __name__ == "__main__":
    main()
