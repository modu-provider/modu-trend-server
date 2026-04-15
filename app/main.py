from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import inspect, literal, select, text
from sqlalchemy.sql import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, engine
from app.models import AudienceGroup, Base, Post, User
from app.scheduler import crawl_once, start_scheduler
from app.services.ingest import get_rankings, recompute_rankings
from app.services.auth import create_access_token, decode_access_token, hash_password, verify_password

app = FastAPI(title="modu-trend")

_scheduler = None
_db_ready = False


def _migrate_keyword_rankings_window_minutes() -> None:
    """기존 window_hours 컬럼·제약을 window_minutes로 교체(랭킹 행은 삭제)."""
    insp = inspect(engine)
    if "keyword_rankings" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("keyword_rankings")}
    if "window_hours" not in cols:
        return
    dialect = engine.dialect.name
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE keyword_rankings DROP CONSTRAINT IF EXISTS uq_kw_group_age_window_keyword"))
        conn.execute(text("DELETE FROM keyword_rankings"))
        if dialect == "postgresql":
            conn.execute(text("ALTER TABLE keyword_rankings DROP COLUMN window_hours"))
            if "window_minutes" not in cols:
                conn.execute(
                    text("ALTER TABLE keyword_rankings ADD COLUMN window_minutes DOUBLE PRECISION NOT NULL DEFAULT 1440")
                )
                conn.execute(text("ALTER TABLE keyword_rankings ALTER COLUMN window_minutes DROP DEFAULT"))
            exists = conn.execute(
                text(
                    "SELECT 1 FROM pg_constraint WHERE conname = 'uq_kw_group_age_window_minutes_keyword'"
                )
            ).scalar()
            if not exists:
                conn.execute(
                    text(
                        "ALTER TABLE keyword_rankings ADD CONSTRAINT uq_kw_group_age_window_minutes_keyword "
                        'UNIQUE ("group", age, window_minutes, keyword)'
                    )
                )
        elif dialect == "sqlite":
            conn.execute(text("ALTER TABLE keyword_rankings DROP COLUMN window_hours"))
            if "window_minutes" not in cols:
                conn.execute(
                    text("ALTER TABLE keyword_rankings ADD COLUMN window_minutes REAL NOT NULL DEFAULT 1440")
                )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_kw_group_age_window_minutes_keyword "
                    "ON keyword_rankings (\"group\", age, window_minutes, keyword)"
                )
            )

bearer = HTTPBearer(auto_error=False)

_cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        user_id = decode_access_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PostHit(BaseModel):
    title: str
    category: str
    source: str
    fetched_at: datetime


class SentimentOut(BaseModel):
    keyword: str
    group: AudienceGroup
    age: int
    window_minutes: float
    matched_posts: int
    analyzed_posts: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float


class NaverDatalabIn(BaseModel):
    keyword: str = Field(min_length=1, max_length=80)


@app.on_event("startup")
def _startup() -> None:
    global _scheduler
    global _db_ready
    try:
        # 빠르게 연결 체크(없으면 startup이 무한 대기하지 않게)
        with engine.connect() as c:
            c.execute(text("select 1"))
        Base.metadata.create_all(bind=engine)
        _migrate_keyword_rankings_window_minutes()
        _scheduler = start_scheduler()
        _db_ready = True
    except SQLAlchemyError:
        # DB가 준비되지 않으면 서버는 뜨되, 기능 API는 503로 처리
        _db_ready = False


@app.on_event("shutdown")
def _shutdown() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "db_ready": str(_db_ready).lower(), "database_url": settings.database_url.split("@")[-1]}


@app.post("/auth/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if not _db_ready:
        raise HTTPException(status_code=503, detail="DB is not ready. Start PostgreSQL and set DATABASE_URL.")
    exists = db.execute(text("select 1 from users where email = :e"), {"e": str(payload.email)}).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")

    u = User(email=str(payload.email), password_hash=hash_password(payload.password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "email": u.email}


@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    if not _db_ready:
        raise HTTPException(status_code=503, detail="DB is not ready. Start PostgreSQL and set DATABASE_URL.")
    row = db.execute(text("select id, password_hash from users where email = :e"), {"e": str(payload.email)}).first()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user_id, password_hash_db = row
    if not verify_password(payload.password, password_hash_db):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenOut(access_token=create_access_token(user_id=int(user_id)))


@app.get("/auth/me")
def me(user: User = Depends(require_user)):
    return {"id": user.id, "email": user.email}


@app.get("/rankings")
def rankings(
    group: AudienceGroup,
    age: int = 20,
    limit: int | None = None,
    minutes: float | None = None,
    user: User = Depends(require_user),
):
    if not _db_ready:
        raise HTTPException(status_code=503, detail="DB is not ready. Start PostgreSQL and set DATABASE_URL.")
    limit = limit or settings.ranking_limit
    window_minutes = minutes if minutes is not None else settings.ranking_window_minutes
    with SessionLocal() as db:
        rows = get_rankings(db, group=group, age=age, window_minutes=window_minutes, limit=limit)
        # 아직 계산된 적이 없으면 즉시 계산
        if not rows:
            recompute_rankings(db, group=group, age=age, window_minutes=window_minutes, limit=limit)
            rows = get_rankings(db, group=group, age=age, window_minutes=window_minutes, limit=limit)
    return {"group": group.value, "age": age, "window_minutes": window_minutes, "items": rows}


@app.get("/posts/search", response_model=SentimentOut)
def search_posts_by_keyword(
    keyword: str,
    group: AudienceGroup,
    age: int = 20,
    limit: int = 50,
    minutes: float | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Analyze sentiment distribution (positive/neutral/negative %) for recent posts matching `keyword`.
    Matching is an exact token match (case-insensitive) against comma-separated `Post.keywords`,
    constrained by audience group/age and fetched_at within the recent window.
    """
    if not _db_ready:
        raise HTTPException(status_code=503, detail="DB is not ready. Start PostgreSQL and set DATABASE_URL.")
    kw = (keyword or "").strip().lower()
    if not kw:
        raise HTTPException(status_code=422, detail="keyword is required")
    if limit <= 0:
        raise HTTPException(status_code=422, detail="limit must be > 0")
    limit = min(limit, 200)

    window_minutes = minutes if minutes is not None else settings.ranking_window_minutes
    since = datetime.now(timezone.utc) - timedelta(minutes=float(window_minutes))

    # Match exact token within comma-separated string.
    # We wrap keywords with commas to avoid partial matches (e.g., "ai" matching "hail").
    wrapped = func.lower(literal(",") + Post.keywords + literal(","))
    token_match = wrapped.like(f"%,{kw},%")

    q = (
        select(Post.title, Post.category, Post.source, Post.fetched_at)
        .where(Post.group == group, Post.age == age, Post.fetched_at >= since, token_match)
        .order_by(Post.fetched_at.desc(), Post.id.desc())
        .limit(limit)
    )
    rows = db.execute(q).all()

    titles = [t for (t, _c, _s, _fa) in rows if t]
    from app.services.sentiment import analyze_title_sentiment_distribution

    try:
        dist = analyze_title_sentiment_distribution(titles)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"sentiment analysis failed: {e}")

    return SentimentOut(
        keyword=kw,
        group=group,
        age=age,
        window_minutes=float(window_minutes),
        matched_posts=len(rows),
        analyzed_posts=len(titles),
        positive_pct=dist.positive_pct,
        neutral_pct=dist.neutral_pct,
        negative_pct=dist.negative_pct,
    )


@app.post("/crawl/now")
def crawl_now():
    if not _db_ready:
        raise HTTPException(status_code=503, detail="DB is not ready. Start PostgreSQL and set DATABASE_URL.")
    try:
        result = crawl_once()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@app.post("/naver/datalab/search")
def naver_datalab_search(payload: NaverDatalabIn, user: User = Depends(require_user)):
    if not _db_ready:
        raise HTTPException(status_code=503, detail="DB is not ready. Start PostgreSQL and set DATABASE_URL.")
    from app.services.naver_datalab import fetch_datalab_search

    try:
        return fetch_datalab_search(keyword=payload.keyword)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"naver datalab call failed: {e}")

