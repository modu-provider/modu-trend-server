from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

from app.config import settings
from app.crawlers.cook82 import crawl_82cook_hot
from app.crawlers.dogdrip import crawl_dogdrip_hot
from app.crawlers.fmkorea import crawl_fmkorea_best2
from app.crawlers.instiz import crawl_instiz_hot
from app.crawlers.theqoo import crawl_theqoo_hot
from app.db import SessionLocal
from app.models import AudienceGroup
from app.services.ingest import recompute_rankings, save_posts, save_posts_multi_age

_EMPTY_SAVE = {
    "skipped_transform_error": 0,
    "skipped_transform_none": 0,
    "skipped_duplicate": 0,
}


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

    disabled_sources: list[str] = []

    with SessionLocal() as db:
        # 20~30대 여성: instiz + theqoo
        if settings.crawl_enable_instiz:
            _ingest(
                "instiz_female_inserted",
                crawl_instiz_hot,
                group=AudienceGroup.female,
                age=20,
                source="instiz",
            )
        else:
            disabled_sources.append("instiz")
            results["instiz_female_inserted"] = 0
            results["instiz_female_crawled"] = 0
            results["instiz_female_save"] = dict(_EMPTY_SAVE)

        if settings.crawl_enable_theqoo:
            try:
                theqoo_items = crawl_theqoo_hot()
                n_theqoo = len(theqoo_items)
                results["theqoo_female_crawled"] = n_theqoo
                results["theqoo_female_30_crawled"] = n_theqoo
                tq_by_age = save_posts_multi_age(
                    db,
                    group=AudienceGroup.female,
                    source="theqoo",
                    items=theqoo_items,
                    ages=(20, 30),
                )
                sp_tq20 = tq_by_age[20]
                sp_tq30 = tq_by_age[30]
                results["theqoo_female_inserted"] = sp_tq20.inserted
                results["theqoo_female_save"] = {
                    "skipped_transform_error": sp_tq20.skipped_transform_error,
                    "skipped_transform_none": sp_tq20.skipped_transform_none,
                    "skipped_duplicate": sp_tq20.skipped_duplicate,
                }
                results["theqoo_female_30_inserted"] = sp_tq30.inserted
                results["theqoo_female_30_save"] = {
                    "skipped_transform_error": sp_tq30.skipped_transform_error,
                    "skipped_transform_none": sp_tq30.skipped_transform_none,
                    "skipped_duplicate": sp_tq30.skipped_duplicate,
                }
            except Exception as e:
                results["theqoo_female_inserted"] = 0
                results["theqoo_female_30_inserted"] = 0
                results["theqoo_female_crawled"] = None
                results["theqoo_female_30_crawled"] = None
                msg = f"theqoo_female: {e}"
                errors.append(msg)
                logger.warning("crawl_once %s", msg, exc_info=True)
        else:
            disabled_sources.append("theqoo")
            results["theqoo_female_inserted"] = 0
            results["theqoo_female_30_inserted"] = 0
            results["theqoo_female_crawled"] = 0
            results["theqoo_female_30_crawled"] = 0
            results["theqoo_female_save"] = dict(_EMPTY_SAVE)
            results["theqoo_female_30_save"] = dict(_EMPTY_SAVE)

        if settings.crawl_enable_82cook:
            _ingest(
                "82cook_female_inserted",
                crawl_82cook_hot,
                group=AudienceGroup.female,
                age=50,
                source="82cook",
            )
        else:
            disabled_sources.append("82cook")
            results["82cook_female_inserted"] = 0
            results["82cook_female_crawled"] = 0
            results["82cook_female_save"] = dict(_EMPTY_SAVE)

        # 에펨코리아 베스트: 크롤·LLM 1회, 20·30대 남성 각각 저장
        if settings.crawl_enable_fmkorea:
            try:
                fm_items = crawl_fmkorea_best2()
                n_fm = len(fm_items)
                results["fmkorea_male_crawled"] = n_fm
                results["fmkorea_male_30_crawled"] = n_fm
                fm_by_age = save_posts_multi_age(
                    db,
                    group=AudienceGroup.male,
                    source="fmkorea",
                    items=fm_items,
                    ages=(20, 30),
                )
                sp_fm20 = fm_by_age[20]
                sp_fm30 = fm_by_age[30]
                results["fmkorea_male_inserted"] = sp_fm20.inserted
                results["fmkorea_male_save"] = {
                    "skipped_transform_error": sp_fm20.skipped_transform_error,
                    "skipped_transform_none": sp_fm20.skipped_transform_none,
                    "skipped_duplicate": sp_fm20.skipped_duplicate,
                }
                results["fmkorea_male_30_inserted"] = sp_fm30.inserted
                results["fmkorea_male_30_save"] = {
                    "skipped_transform_error": sp_fm30.skipped_transform_error,
                    "skipped_transform_none": sp_fm30.skipped_transform_none,
                    "skipped_duplicate": sp_fm30.skipped_duplicate,
                }
            except Exception as e:
                results["fmkorea_male_inserted"] = 0
                results["fmkorea_male_30_inserted"] = 0
                results["fmkorea_male_crawled"] = None
                results["fmkorea_male_30_crawled"] = None
                msg = f"fmkorea_male: {e}"
                errors.append(msg)
                logger.warning("crawl_once %s", msg, exc_info=True)
        else:
            disabled_sources.append("fmkorea")
            results["fmkorea_male_inserted"] = 0
            results["fmkorea_male_30_inserted"] = 0
            results["fmkorea_male_crawled"] = 0
            results["fmkorea_male_30_crawled"] = 0
            results["fmkorea_male_save"] = dict(_EMPTY_SAVE)
            results["fmkorea_male_30_save"] = dict(_EMPTY_SAVE)

        # 30대 남성 커뮤니티: 개드립 인기글
        if settings.crawl_enable_dogdrip:
            _ingest(
                "dogdrip_male_inserted",
                crawl_dogdrip_hot,
                group=AudienceGroup.male,
                age=30,
                source="dogdrip",
            )
        else:
            disabled_sources.append("dogdrip")
            results["dogdrip_male_inserted"] = 0
            results["dogdrip_male_crawled"] = 0
            results["dogdrip_male_save"] = dict(_EMPTY_SAVE)

        # rankings refresh (일부 소스 실패해도 가능한 만큼 갱신)
        _recompute(
            "rankings_female_20",
            group=AudienceGroup.female,
            age=20,
            window_minutes=settings.ranking_window_minutes,
            limit=settings.ranking_limit,
        )
        _recompute(
            "rankings_female_30",
            group=AudienceGroup.female,
            age=30,
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
        _recompute(
            "rankings_male_30",
            group=AudienceGroup.male,
            age=30,
            window_minutes=settings.ranking_window_minutes,
            limit=settings.ranking_limit,
        )

    results["ran_at"] = int(datetime.utcnow().timestamp())
    if disabled_sources:
        results["crawl_disabled_sources"] = disabled_sources
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

