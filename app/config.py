from __future__ import annotations

import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 기본은 PostgreSQL. 로컬에 Postgres가 없으면 개발용으로 sqlite로도 실행 가능:
    # sqlite:///./dev.db
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/modutradb?connect_timeout=5"

    # 분 단위(소수 가능, 예: 0.5 = 30초). 스케줄러는 초로 변환해 사용.
    crawl_interval_min_minutes: float = 10.0
    crawl_interval_max_minutes: float = 30.0

    # 커뮤니티별 크롤 on/off (.env: CRAWL_ENABLE_INSTIZ=false 등)
    crawl_enable_instiz: bool = True
    crawl_enable_theqoo: bool = True
    crawl_enable_82cook: bool = True
    crawl_enable_fmkorea: bool = True
    crawl_enable_dogdrip: bool = True
    crawl_enable_ruliweb: bool = True
    crawl_enable_ilbe: bool = True

    # 랭킹 집계 윈도우(분, 소수 가능). 환경변수 RANKING_WINDOW_HOURS만 있으면 분으로 환산(×60).
    ranking_window_minutes: float = 1440.0
    ranking_limit: int = 10

    @model_validator(mode="after")
    def _legacy_ranking_window_hours_env(self) -> "Settings":
        if os.getenv("RANKING_WINDOW_MINUTES") is None and os.getenv("RANKING_WINDOW_HOURS") is not None:
            object.__setattr__(self, "ranking_window_minutes", float(os.environ["RANKING_WINDOW_HOURS"]) * 60.0)
        return self

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_moderation_model: str = "omni-moderation-latest"
    openai_transform_enabled: bool = True

    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"

    # comma-separated origins (e.g. "http://localhost:3000,http://127.0.0.1:5173")
    cors_allow_origins: str = "*"


settings = Settings()

