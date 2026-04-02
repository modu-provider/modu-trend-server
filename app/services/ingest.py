from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crawlers.common import CrawledItem
from app.models import AudienceGroup, KeywordRanking, Post
from app.services.keywords import top_keywords
from app.services.transform import transform_title_and_category


def _hash(source: str, age: int, title: str, category: str) -> str:
    raw = f"{source}|{age}|{title}|{category}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SavePostsResult:
    inserted: int
    """OpenAI 호출 예외(JSON/네트워크/API 키 등)."""
    skipped_transform_error: int
    """모더레이션 차단, 모델 skip:true, 빈 제목 등 변환 결과 없음."""
    skipped_transform_none: int
    """이미 같은 원문 해시(uq_posts)가 있음."""
    skipped_duplicate: int


def save_posts(
    db: Session,
    *,
    group: AudienceGroup,
    age: int,
    source: str,
    items: list[CrawledItem],
) -> SavePostsResult:
    inserted = 0
    skipped_transform_error = 0
    skipped_transform_none = 0
    skipped_duplicate = 0
    for it in items:
        # 원문은 저장하지 않고, OpenAI 변환 결과만 저장
        try:
            tr = transform_title_and_category(title=it.title, category=it.category or "")
        except Exception:
            skipped_transform_error += 1
            continue
        if tr is None:
            skipped_transform_none += 1
            continue

        p = Post(
            group=group,
            age=age,
            source=source,
            title=tr.title[:512],
            category=tr.category[:128],
            keywords=",".join(tr.keywords)[:512],
            content_hash=_hash(source, age, it.title, it.category or ""),
        )
        db.add(p)
        try:
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()
            skipped_duplicate += 1
    return SavePostsResult(
        inserted=inserted,
        skipped_transform_error=skipped_transform_error,
        skipped_transform_none=skipped_transform_none,
        skipped_duplicate=skipped_duplicate,
    )


def recompute_rankings(
    db: Session,
    *,
    group: AudienceGroup,
    age: int,
    window_minutes: float,
    limit: int,
) -> list[tuple[str, int]]:
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    rows = db.execute(
        select(Post.title, Post.category, Post.keywords).where(
            Post.group == group, Post.age == age, Post.fetched_at >= since
        )
    ).all()
    texts = []
    keywords_only: list[str] = []
    for title, category, keywords in rows:
        if keywords:
            # comma-separated keywords
            keywords_only.extend([k.strip() for k in keywords.split(",") if k.strip()])
        else:
            texts.append(f"{title} {category}".strip())

    if keywords_only:
        from collections import Counter

        c = Counter([k.lower() for k in keywords_only if len(k) >= 2])
        top = c.most_common(limit)
    else:
        top = top_keywords(texts, limit=limit)

    db.execute(
        delete(KeywordRanking).where(
            KeywordRanking.group == group, KeywordRanking.age == age, KeywordRanking.window_minutes == window_minutes
        )
    )
    db.commit()

    now = datetime.now(timezone.utc)
    for kw, cnt in top:
        db.add(
            KeywordRanking(
                group=group,
                age=age,
                window_minutes=window_minutes,
                keyword=kw[:64],
                count=cnt,
                calculated_at=now,
            )
        )
    db.commit()
    return top


def get_rankings(
    db: Session,
    *,
    group: AudienceGroup,
    age: int,
    window_minutes: float,
    limit: int,
) -> list[dict[str, int | str]]:
    q = (
        select(KeywordRanking.keyword, KeywordRanking.count)
        .where(KeywordRanking.group == group, KeywordRanking.age == age, KeywordRanking.window_minutes == window_minutes)
        .order_by(KeywordRanking.count.desc(), KeywordRanking.keyword.asc())
        .limit(limit)
    )
    rows = db.execute(q).all()
    return [{"keyword": k, "count": c} for (k, c) in rows]

