import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


BASE_URL = "https://bbs.ruliweb.com/best/all"


@dataclass
class PostItem:
    title: str
    url: str
    views: Optional[int]
    upvotes: Optional[int]
    comments: Optional[int]
    author: Optional[str]
    time: Optional[str]


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
            "Referer": "https://bbs.ruliweb.com/",
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


def fetch_html(session: requests.Session, url: str, params: Optional[dict] = None) -> str:
    response = session.get(url, params=params or {}, timeout=10)
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
    # Try multiple known structures for Ruliweb lists
    containers: Iterable = []
    candidates = [
        "div.board_main div.board_list div.table_body div.table_row",  # common table layout
        "div.board_main div.board_list div.table_row",  # variant
        "div.board_main li",  # fallback
        "div.board_list div.table_body > div",  # generic rows
        "div.list_body > div",  # generic alternative
        "article.list_item",  # rare alternative
    ]

    for selector in candidates:
        found = soup.select(selector)
        if found:
            containers = found
            break

    posts: List[PostItem] = []

    for row in containers:
        classes = " ".join(row.get("class", []))
        if "notice" in classes or "ad" in classes:
            continue

        # Title and link
        title_el = (
            row.select_one("a.deco") or row.select_one("a.subject_link") or row.select_one("a[href*='/best/']")
        )
        if not title_el:
            continue
        title = (title_el.get_text(strip=True) or "").strip()
        href = title_el.get("href") or ""
        if href.startswith("/"):
            url = f"https://bbs.ruliweb.com{href}"
        elif href.startswith("http"):
            url = href
        else:
            url = f"https://bbs.ruliweb.com/{href}".rstrip("/")

        # Views (readcount), often in .hit or .view or [data-role='list-count']
        views_el = row.select_one(".hit") or row.select_one(".view") or row.select_one("[data-role='list-count']")
        views = parse_int_safe(views_el.get_text(strip=True) if views_el else None)

        # Upvotes (recommend), often in .recom or .vote or .recommend
        upvote_el = row.select_one(".recom") or row.select_one(".vote") or row.select_one(".recommend")
        upvotes = parse_int_safe(upvote_el.get_text(strip=True) if upvote_el else None)

        # Comments near title often in .num or .reply or .comment
        comment_el = (
            row.select_one(".num") or row.select_one(".reply") or row.select_one(".comment") or row.select_one(".cmt")
        )
        comments = parse_int_safe(comment_el.get_text(strip=True) if comment_el else None)

        # Author and time
        author_el = row.select_one(".writer") or row.select_one(".nick") or row.select_one(".author")
        author = author_el.get_text(strip=True) if author_el else None

        time_el = row.select_one(".time") or row.select_one("time") or row.select_one(".regdate")
        time_text = (
            time_el.get("datetime") if time_el and time_el.has_attr("datetime") else (time_el.get_text(strip=True) if time_el else None)
        )

        posts.append(
            PostItem(
                title=title,
                url=url,
                views=views,
                upvotes=upvotes,
                comments=comments,
                author=author,
                time=time_text,
            )
        )

    # Fallback: scan anchor tags if parsing failed
    if not posts:
        for a in soup.select("a[href*='/best/']"):
            title = a.get_text(strip=True)
            href = a.get("href") or ""
            url = f"https://bbs.ruliweb.com{href}" if href.startswith("/") else href
            if title and url and "/read/" in url:
                posts.append(PostItem(title=title, url=url, views=None, upvotes=None, comments=None, author=None, time=None))

    return posts


def crawl_ruliweb_best(orderby: str = "readcount", range_value: Optional[str] = None, limit: int = 30) -> List[PostItem]:
    session = create_http_session()
    params = {"orderby": orderby}
    if range_value:
        params["range"] = range_value
    html = fetch_html(session, BASE_URL, params=params)
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
        if p.views is not None:
            meta_parts.append(f"👁️ {p.views}")
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


def print_titles_only(posts: List[PostItem]) -> None:
    if not posts:
        return
    for p in posts:
        print(p.title)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl Ruliweb Best and print posts.")
    parser.add_argument("--limit", type=int, default=30, help="Number of posts to show (default: 30)")
    parser.add_argument("--orderby", type=str, default="readcount", help="Order by: readcount, recommend, comment, etc.")
    parser.add_argument("--range", dest="range_value", type=str, default=None, help="Range parameter (e.g., 24, 12h, 7d).")
    args = parser.parse_args(argv)

    try:
        posts = crawl_ruliweb_best(orderby=args.orderby, range_value=args.range_value, limit=args.limit)
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 2
    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1

    # Always print only titles
    print_titles_only(posts)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
