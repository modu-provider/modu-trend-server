from __future__ import annotations

from datetime import datetime, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings

# Windows 환경에서 bcrypt 백엔드 설치/로드 문제를 피하기 위해
# 순수 파이썬으로 동작하는 PBKDF2(SHA-256)를 사용
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(*, user_id: int) -> str:
    now = datetime.now(timezone.utc)
    # no expiry
    payload = {"sub": str(user_id), "iat": int(now.timestamp())}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    sub = payload.get("sub")
    if not sub or not str(sub).isdigit():
        raise jwt.InvalidTokenError("invalid sub")
    return int(sub)

