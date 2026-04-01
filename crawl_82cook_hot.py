"""82cook.com 최근 많이 읽은 글 크롤링 (로컬 테스트용). 프로젝트 루트에서 실행: python crawl_82cook_hot.py"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.crawlers.cook82 import crawl_82cook_hot  # noqa: E402


def main() -> None:
    items = crawl_82cook_hot()
    for it in items:
        print(f"{it.title}\t[{it.category}]")
    print(f"total: {len(items)}")


if __name__ == "__main__":
    main()
