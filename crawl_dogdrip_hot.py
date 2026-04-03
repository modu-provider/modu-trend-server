"""dogdrip.net 개드립 인기글 크롤링 (로컬 테스트). 프로젝트 루트: python crawl_dogdrip_hot.py"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.crawlers.dogdrip import crawl_dogdrip_hot  # noqa: E402


def main() -> None:
    items = crawl_dogdrip_hot()
    for it in items:
        print(it.title)
    print(f"\ntotal: {len(items)}")


if __name__ == "__main__":
    main()
