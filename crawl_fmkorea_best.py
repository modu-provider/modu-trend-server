"""
테스트용: FM코리아 포텐 터짐 화제순(best2) 목록을 가져와 콘솔에 출력합니다.

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

BEST2_URL = "https://www.fmkorea.com/best2"
# 사이트가 일부 브라우저형 UA에서 HTTP 430을 반환할 수 있어 짧은 UA 사용
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def fetch_html(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_best_posts(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    widget = soup.select_one("div.fm_best_widget._bd_pc ul, div.fm_best_widget ul")
    if not widget:
        return []

    rows: list[dict[str, str]] = []
    for li in widget.select("li.li"):
        title_a = li.select_one("h3.title a[href^='/best2/']")
        if not title_a:
            continue
        title_el = title_a.select_one("span.ellipsis-target")
        title = (title_el.get_text(strip=True) if title_el else title_a.get_text(" ", strip=True))
        cat_el = li.select_one("span.category")
        category = cat_el.get_text(" ", strip=True) if cat_el else ""

        rows.append(
            {
                "title": title,
                "category": category,
            }
        )
    return rows


def main() -> None:
    print(f"요청: {BEST2_URL}\n")
    html = fetch_html(BEST2_URL)
    posts = parse_best_posts(html)
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
