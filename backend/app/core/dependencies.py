import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JOSEError, JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, is_token_blacklisted
from app.db.models.user import User, UserRole
from app.db.redis import get_redis
from app.db.repositories.user_repository import UserRepository
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        jti: str | None = payload.get("jti")
        if not user_id or token_type != "access":
            raise _credentials_exception
    except JWTError:
        raise _credentials_exception

    if jti and await is_token_blacklisted(jti, redis):
        raise _credentials_exception

    user = await UserRepository(db).get_by_id(uuid.UUID(user_id))
    if not user:
        raise _credentials_exception
    return user


async def get_optional_user(
    token: str | None = Depends(optional_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")
        if not user_id or payload.get("type") != "access":
            return None
        if jti and await is_token_blacklisted(jti, redis):
            return None
        return await UserRepository(db).get_by_id(uuid.UUID(user_id))
    except (JOSEError, ValueError):
        # JOSEError covers JWTError; ValueError covers malformed UUID in `sub`.
        return None


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


async def get_current_admin(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges")
    return current_user


async def get_current_customer(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins cannot make or hold bookings",
        )
    return current_user


async def get_current_verified_customer(current_user: User = Depends(get_current_customer)) -> User:
    if not current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before booking.",
        )
    return current_user
