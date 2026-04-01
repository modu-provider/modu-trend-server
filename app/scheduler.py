from __future__ import annotations

import random
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.crawlers.cook82 import crawl_82cook_hot
from app.crawlers.fmkorea import crawl_fmkorea_best2
from app.crawlers.instiz import crawl_instiz_hot
from app.crawlers.theqoo import crawl_theqoo_hot
from app.db import SessionLocal
from app.models import AudienceGroup
from app.services.ingest import recompute_rankings, save_posts


def crawl_once() -> dict[str, int]:
    results: dict[str, int] = {}
    with SessionLocal() as db:
        # 20~30대 여성: instiz + theqoo
        results["instiz_female_inserted"] = save_posts(
            db, group=AudienceGroup.female, age=20, source="instiz", items=crawl_instiz_hot()
        )
        results["theqoo_female_inserted"] = save_posts(
            db, group=AudienceGroup.female, age=20, source="theqoo", items=crawl_theqoo_hot()
        )
        results["82cook_female_inserted"] = save_posts(
            db, group=AudienceGroup.female, age=20, source="82cook", items=crawl_82cook_hot()
        )

        # 20~30대 남성: fmkorea
        results["fmkorea_male_inserted"] = save_posts(
            db, group=AudienceGroup.male, age=20, source="fmkorea", items=crawl_fmkorea_best2()
        )

        # rankings refresh
        recompute_rankings(
            db,
            group=AudienceGroup.female,
            age=20,
            window_minutes=settings.ranking_window_minutes,
            limit=settings.ranking_limit,
        )
        recompute_rankings(
            db,
            group=AudienceGroup.male,
            age=20,
            window_minutes=settings.ranking_window_minutes,
            limit=settings.ranking_limit,
        )

    results["ran_at"] = int(datetime.utcnow().timestamp())
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

