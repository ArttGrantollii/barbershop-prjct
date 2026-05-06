import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt
from redis.asyncio import Redis

from app.core.config import settings

_BLACKLIST_PREFIX = "blacklist"


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(subject: str | Any) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(subject), "exp": expire, "type": "access", "jti": str(uuid.uuid4())},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(subject: str | Any) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(subject), "exp": expire, "type": "refresh", "jti": str(uuid.uuid4())},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


async def blacklist_token(jti: str, exp: datetime, redis: Redis) -> None:
    ttl = int((exp - datetime.now(timezone.utc)).total_seconds())
    if ttl > 0:
        await redis.setex(f"{_BLACKLIST_PREFIX}:{jti}", ttl, "1")


async def is_token_blacklisted(jti: str, redis: Redis) -> bool:
    return await redis.exists(f"{_BLACKLIST_PREFIX}:{jti}") == 1
