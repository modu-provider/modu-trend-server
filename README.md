# modu-trend

FastAPI + PostgreSQL 서버에서 커뮤니티(인스티즈/더쿠/에펨코리아) 인기글을 주기적으로 크롤링해 DB에 저장하고,
20~30대 여성/남성이 주목하는 키워드 TOP 10을 제공합니다.

## 실행

- PostgreSQL 실행

```bash
docker compose up -d
```

- 의존성 설치

```bash
pip install -r requirements.txt
```

- 환경변수 설정

`.env.example` 참고해서 `.env`를 만들거나 환경변수로 `DATABASE_URL`을 지정하세요.

- 서버 실행

```bash
uvicorn app.main:app --reload
```

## API

- `GET /health`
- `GET /rankings?group=female|male&limit=10&minutes=1440` (`RANKING_WINDOW_MINUTES` 기본값 사용 가능)
- `POST /crawl/now` (즉시 크롤링 + 랭킹 갱신)

