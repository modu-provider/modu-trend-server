from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AudienceGroup(str, enum.Enum):
    female = "female"  # 20~30대 여성
    male = "male"  # 20~30대 남성


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("group", "age", "source", "content_hash", name="uq_posts_group_age_source_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group: Mapped[AudienceGroup] = mapped_column(Enum(AudienceGroup, name="audience_group"), index=True)
    age: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String(32), index=True)  # instiz/theqoo/fmkorea

    title: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(128), default="")
    keywords: Mapped[str] = mapped_column(String(512), default="")  # comma-separated

    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class KeywordRanking(Base):
    __tablename__ = "keyword_rankings"
    __table_args__ = (
        UniqueConstraint("group", "age", "window_minutes", "keyword", name="uq_kw_group_age_window_minutes_keyword"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group: Mapped[AudienceGroup] = mapped_column(Enum(AudienceGroup, name="audience_group"), index=True)
    age: Mapped[int] = mapped_column(Integer, index=True)
    window_minutes: Mapped[float] = mapped_column(Float, index=True)

    keyword: Mapped[str] = mapped_column(String(64), index=True)
    count: Mapped[int] = mapped_column(Integer)

    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

