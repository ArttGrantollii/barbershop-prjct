import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models.user import AccountTokenPurpose, User
from app.db.repositories.account_token_repository import AccountTokenRepository
from app.db.repositories.user_repository import UserRepository
from app.notifications.schemas import AccountActionInfo
from app.notifications.service import notify_email_verification, notify_password_reset


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _frontend_url(path: str, token: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/") + "/"
    return urljoin(base, f"{path.lstrip('/')}?token={token}")


async def send_email_verification(db: AsyncSession, user: User) -> None:
    repo = AccountTokenRepository(db)
    await repo.expire_user_tokens(user.id, AccountTokenPurpose.EMAIL_VERIFICATION)
    raw = _new_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_HOURS)
    await repo.create_token(
        user_id=user.id,
        purpose=AccountTokenPurpose.EMAIL_VERIFICATION,
        token_hash=_hash_token(raw),
        expires_at=expires_at,
    )
    await notify_email_verification(
        AccountActionInfo(
            customer_name=user.name,
            customer_email=user.email,
            action_url=_frontend_url("/verify-email", raw),
            expires_minutes=settings.EMAIL_VERIFICATION_TOKEN_HOURS * 60,
        )
    )


async def verify_email(db: AsyncSession, token: str) -> User:
    repo = AccountTokenRepository(db)
    row = await repo.get_active(_hash_token(token), AccountTokenPurpose.EMAIL_VERIFICATION)
    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link")
    user = await UserRepository(db).get_by_id(row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification link")
    user.is_email_verified = True
    await repo.mark_used(row)
    await db.commit()
    await db.refresh(user)
    return user


async def request_password_reset(db: AsyncSession, email: str) -> None:
    user = await UserRepository(db).get_by_email(email)
    if not user or not user.is_active:
        return
    repo = AccountTokenRepository(db)
    await repo.expire_user_tokens(user.id, AccountTokenPurpose.PASSWORD_RESET)
    raw = _new_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES)
    await repo.create_token(
        user_id=user.id,
        purpose=AccountTokenPurpose.PASSWORD_RESET,
        token_hash=_hash_token(raw),
        expires_at=expires_at,
    )
    await notify_password_reset(
        AccountActionInfo(
            customer_name=user.name,
            customer_email=user.email,
            action_url=_frontend_url("/reset-password", raw),
            expires_minutes=settings.PASSWORD_RESET_TOKEN_MINUTES,
        )
    )


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    repo = AccountTokenRepository(db)
    row = await repo.get_active(_hash_token(token), AccountTokenPurpose.PASSWORD_RESET)
    if not row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link")
    user = await UserRepository(db).get_by_id(row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset link")
    user.hashed_password = get_password_hash(new_password)
    await repo.mark_used(row)
    await db.commit()
