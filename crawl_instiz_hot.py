"""
테스트용: 인스티즈(instiz) 메인 페이지의 '인기글(Realchart)' 목록을 가져와 콘솔에 출력합니다.

의존성: pip install beautifulsoup4
"""

from __future__ import annotations

import sys
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except OSError:
        pass


URL = "https://www.instiz.net/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_html(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_hot(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one("#boardhot")
    if not container:
        return []

    posts: list[dict[str, str]] = []
    for a in container.select("div.realchart_item_a a[href]"):
        rank_el = a.select_one("span.rank")
        title_el = a.select_one("span.post_title")
        if not rank_el or not title_el:
            continue

        rank = rank_el.get_text(strip=True)
        # 여러 탭(일상/연예/드영배 등)까지 같이 잡히므로
        # '전체 인기글'에 해당하는 1~20위만 출력 대상으로 제한
        if not rank.isdigit():
            continue
        rank_num = int(rank)
        if rank_num < 1 or rank_num > 20:
            continue

        category_el = a.select_one("span.minitext")
        category = category_el.get_text(strip=True) if category_el else ""

        # title에 아이콘(i/img 등)이 섞여있어서 text만 깔끔하게 추출
        title = title_el.get_text(" ", strip=True)

        posts.append(
            {
                "rank": rank,
                "category": category,
                "title": title,
            }
        )

    # 같은 rank가 여러 탭에서 반복될 수 있어, rank 기준으로 dedupe
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for p in posts:
        if p["rank"] in seen:
            continue
        seen.add(p["rank"])
        deduped.append(p)
    return deduped


def main() -> None:
    print(f"요청: {URL}\n")
    html = fetch_html(URL)
    posts = parse_hot(html)
    if not posts:
        print("목록을 찾지 못했습니다. (HTML 구조 변경 또는 차단 여부를 확인하세요.)")
        return

    for i, p in enumerate(posts, start=1):
        head = f"[{i:02d}] #{p['rank']}"
        if p["category"]:
            head += f" [{p['category']}]"
        head += f" {p['title']}"
        print(head)
        print()


if __name__ == "__main__":
    main()
