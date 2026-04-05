import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


ARCA_LIVE_URL = "https://arca.live/b/live"


@dataclass
class PostItem:
    title: str
    url: str
    upvotes: Optional[int]
    comments: Optional[int]
    author: Optional[str]
    time: Optional[str]


def create_http_session() -> requests.Session:
    session = requests.Session()
    # Be a polite client; some sites block default UA
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://arca.live/",
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
    response = session.get(url, timeout=10)
    response.raise_for_status()
    return response.text


def parse_int_safe(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    stripped = "".join(ch for ch in text if ch.isdigit())
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def extract_posts(soup: BeautifulSoup) -> List[PostItem]:
    # Arca uses list rows; structure can vary. We try a few selectors robustly.
    containers: Iterable = []

    # Common patterns seen on arca boards
    candidates = [
        "div.list > div > div.vrow",  # rows
        "div.list div.vrow",  # rows
        "div.list-table > div.vrow",  # alternative
        "article.list-item",  # article item variant
        "div.board-body div.vrow",
        "div.vrow",  # fallback, but we will filter
    ]

    for selector in candidates:
        found = soup.select(selector)
        if found:
            containers = found
            break

    posts: List[PostItem] = []

    for c in containers:
        # Skip notice/announcement rows if flagged
        row_classes = " ".join(c.get("class", []))
        if "notice" in row_classes or "ad" in row_classes:
            continue

        # Title and URL
        title_el = (
            c.select_one("a.title") or c.select_one("a.link") or c.select_one("a[href*='/b/']")
        )
        if not title_el:
            continue
        title = (title_el.get_text(strip=True) or "").strip()
        href = title_el.get("href") or ""
        if href.startswith("/"):
            url = f"https://arca.live{href}"
        elif href.startswith("http"):
            url = href
        else:
            url = f"https://arca.live/{href}".rstrip("/")

        # Upvotes / recommendations often shown as .vote or .up / .recommend
        upvote_el = (
            c.select_one(".vote") or c.select_one(".up") or c.select_one(".recommend") or c.select_one(".recommends")
        )
        upvotes = parse_int_safe(upvote_el.get_text(strip=True) if upvote_el else None)

        # Comments count often in .count or .reply or .comments around title
        comment_el = (
            c.select_one(".count") or c.select_one(".reply") or c.select_one(".comments") or c.select_one(".comment")
        )
        comments = parse_int_safe(comment_el.get_text(strip=True) if comment_el else None)

        # Author
        author_el = c.select_one(".user .nick") or c.select_one(".author .nick") or c.select_one(".user") or c.select_one(".author")
        author = author_el.get_text(strip=True) if author_el else None

        # Time
        time_el = c.select_one("time") or c.select_one(".time") or c.select_one(".date")
        time_text = (time_el.get("datetime") if time_el and time_el.has_attr("datetime") else (time_el.get_text(strip=True) if time_el else None))

        posts.append(
            PostItem(
                title=title,
                url=url,
                upvotes=upvotes,
                comments=comments,
                author=author,
                time=time_text,
            )
        )

    # If nothing matched, try a different simple structure as last resort
    if not posts:
        for a in soup.select("a[href^='/b/live/']"):
            title = a.get_text(strip=True)
            href = a.get("href") or ""
            url = f"https://arca.live{href}" if href.startswith("/") else href
            if title and url:
                posts.append(PostItem(title=title, url=url, upvotes=None, comments=None, author=None, time=None))

    return posts


def crawl_arca_live(limit: int = 30) -> List[PostItem]:
    session = create_http_session()
    html = fetch_html(session, ARCA_LIVE_URL)
    soup = BeautifulSoup(html, "html.parser")
    posts = extract_posts(soup)
    if limit > 0:
        posts = posts[:limit]
    return posts


def print_posts_human_readable(posts: List[PostItem]) -> None:
    if not posts:
        print("No posts found.")
        return

    for idx, p in enumerate(posts, 1):
        meta_parts = []
        if p.upvotes is not None:
            meta_parts.append(f"▲{p.upvotes}")
        if p.comments is not None:
            meta_parts.append(f"💬{p.comments}")
        if p.author:
            meta_parts.append(f"by {p.author}")
        if p.time:
            meta_parts.append(p.time)
        meta = " | ".join(meta_parts)

        print(f"[{idx}] {p.title}")
        if meta:
            print(f"    {meta}")
        print(f"    {p.url}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl arca.live/b/live and print latest posts.")
    parser.add_argument("--limit", type=int, default=30, help="Number of posts to show (default: 30)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args(argv)

    try:
        posts = crawl_arca_live(limit=args.limit)
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 2
    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([asdict(p) for p in posts], ensure_ascii=False, indent=2))
    else:
        print_posts_human_readable(posts)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
