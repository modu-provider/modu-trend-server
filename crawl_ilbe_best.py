import argparse
import sys
from typing import List, Optional

import requests

from app.crawlers.common import CrawledItem
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


BASE_URL = "https://www.ilbe.com/list/ilbe"


def create_http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.ilbe.com/",
        }
    )

    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_html(session: requests.Session, url: str) -> str:
    resp = session.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


def extract_titles(soup: BeautifulSoup) -> List[str]:
    titles: List[str] = []

    # Known/likely selectors for list titles on ilbe
    candidates = [
        "div.board-list div.board-body a.subject",  # common
        "div.board-list a.subject",
        "table.board-list a.subject",
        "ul.board-list a.subject",
        "a.subject",  # fallback
    ]
    rows: List = []
    for sel in candidates:
        found = soup.select(sel)
        if found:
            rows = found
            break

    for a in rows:
        text = a.get_text(strip=True)
        if text:
            titles.append(text)

    # Last resort: any anchors containing a data-role or subject-like class
    if not titles:
        for a in soup.select("a"):
            cls = " ".join(a.get("class", []))
            if "subject" in cls:
                text = a.get_text(strip=True)
                if text:
                    titles.append(text)

    return titles


def crawl_ilbe_titles(limit: int = 30) -> List[CrawledItem]:
    session = create_http_session()
    html = fetch_html(session, BASE_URL)
    soup = BeautifulSoup(html, "html.parser")
    titles = extract_titles(soup)
    if limit > 0:
        titles = titles[:limit]
    return [CrawledItem(title=t, category="") for t in titles]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl ilbe list and print titles only.")
    parser.add_argument("--limit", type=int, default=30, help="Number of titles to show (default: 30)")
    args = parser.parse_args(argv)

    try:
        items = crawl_ilbe_titles(limit=args.limit)
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 2
    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1

    for it in items:
        print(it.title)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
