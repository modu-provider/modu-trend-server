from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

from app.config import settings
from app.crawlers.cook82 import crawl_82cook_hot
from app.crawlers.fmkorea import crawl_fmkorea_best2
from app.crawlers.instiz import crawl_instiz_hot
from app.crawlers.theqoo import crawl_theqoo_hot
from app.db import SessionLocal
from app.models import AudienceGroup
from app.services.ingest import recompute_rankings, save_posts


def crawl_once() -> dict[str, Any]:
    results: dict[str, Any] = {}
    errors: list[str] = []

    def _ingest(key: str, crawl_fn, *, group: AudienceGroup, age: int, source: str) -> None:
        crawled_key = key.replace("_inserted", "_crawled")
        try:
            items = crawl_fn()
            results[crawled_key] = len(items)
            sp = save_posts(db, group=group, age=age, source=source, items=items)
            results[key] = sp.inserted
            save_key = key.replace("_inserted", "_save")
            results[save_key] = {
                "skipped_transform_error": sp.skipped_transform_error,
                "skipped_transform_none": sp.skipped_transform_none,
                "skipped_duplicate": sp.skipped_duplicate,
            }
        except Exception as e:
            results[key] = 0
            results[crawled_key] = None
            msg = f"{key}: {e}"
            errors.append(msg)
            logger.warning("crawl_once %s", msg, exc_info=True)

    def _recompute(label: str, **kw: Any) -> None:
        try:
            recompute_rankings(db, **kw)
        except Exception as e:
            errors.append(f"{label}: {e}")
            logger.warning("crawl_once %s: %s", label, e, exc_info=True)

    with SessionLocal() as db:
        # 20~30대 여성: instiz + theqoo
        _ingest(
            "instiz_female_inserted",
            crawl_instiz_hot,
            group=AudienceGroup.female,
            age=20,
            source="instiz",
        )
        _ingest(
            "theqoo_female_inserted",
            crawl_theqoo_hot,
            group=AudienceGroup.female,
            age=20,
            source="theqoo",
        )
        _ingest(
            "82cook_female_inserted",
            crawl_82cook_hot,
            group=AudienceGroup.female,
            age=50,
            source="82cook",
        )

        # 20~30대 남성: fmkorea
        _ingest(
            "fmkorea_male_inserted",
            crawl_fmkorea_best2,
            group=AudienceGroup.male,
            age=20,
            source="fmkorea",
        )

        # rankings refresh (일부 소스 실패해도 가능한 만큼 갱신)
        _recompute(
            "rankings_female_20",
            group=AudienceGroup.female,
            age=20,
            window_minutes=settings.ranking_window_minutes,
            limit=settings.ranking_limit,
        )
        _recompute(
            "rankings_female_50",
            group=AudienceGroup.female,
            age=50,
            window_minutes=settings.ranking_window_minutes,
            limit=settings.ranking_limit,
        )
        _recompute(
            "rankings_male_20",
            group=AudienceGroup.male,
            age=20,
            window_minutes=settings.ranking_window_minutes,
            limit=settings.ranking_limit,
        )

    results["ran_at"] = int(datetime.utcnow().timestamp())
    if errors:
        results["errors"] = errors
    return results


def _random_interval_seconds() -> int:
    lo = settings.crawl_interval_min_minutes * 60.0
    hi = settings.crawl_interval_max_minutes * 60.0
    if lo > hi:
        lo, hi = hi, lo
    secs = int(random.uniform(lo, hi))
    return max(1, secs)


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")

    # interval 랜덤(10~30분): APScheduler interval은 고정이라,
    # 1분마다 체크하면서 확률적으로 실행하는 대신, 실행 때마다 다음 시간을 재예약.
    def _job():
        try:
            crawl_once()
        except Exception:
            # 크롤링/변환 실패가 있더라도 다음 스케줄이 계속 돌도록 보호
            pass
        sched.reschedule_job("crawl_job", trigger="interval", seconds=_random_interval_seconds())

    sched.add_job(
        _job,
        "interval",
        seconds=_random_interval_seconds(),
        id="crawl_job",
        replace_existing=True,
        max_instances=2,
        coalesce=True,
    )
    sched.start()
    return sched

