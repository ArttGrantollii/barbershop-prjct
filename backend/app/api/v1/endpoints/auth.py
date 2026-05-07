import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    optional_oauth2_scheme,
)
from app.core.limiter import limiter
from app.core.security import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    is_token_blacklisted,
    verify_password,
)
from app.db.models.user import User
from app.db.redis import get_redis
from app.db.repositories.user_repository import UserRepository
from app.db.session import get_db
from app.schemas.auth import RefreshTokenRequest, TokenResponse
from app.schemas.user import (
    PasswordChangeRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger(__name__)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    repo = UserRepository(db)
    if await repo.get_by_email(body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = await repo.create(
        name=body.name,
        email=body.email,
        phone=body.phone,
        hashed_password=get_password_hash(body.password),
    )
    logger.info("user_registered", user_id=str(user.id), email=body.email)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    repo = UserRepository(db)
    user = await repo.get_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("login_failed", email=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive account")
    logger.info("user_logged_in", user_id=str(user.id))
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    body: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
    )
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise invalid
        jti: str | None = payload.get("jti")
        user_id: str = payload["sub"]
    except (JWTError, KeyError):
        raise invalid

    if jti and await is_token_blacklisted(jti, redis):
        raise invalid

    user = await UserRepository(db).get_by_id(uuid.UUID(user_id))
    if not user or not user.is_active:
        raise invalid

    # Rotate: blacklist the consumed refresh token so it can't be reused.
    if jti:
        exp_ts = payload.get("exp")
        if exp_ts:
            exp = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            await blacklist_token(jti, exp, redis)

    logger.info("token_refreshed", user_id=user_id)
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def logout(
    request: Request,
    body: RefreshTokenRequest,
    token: str | None = Depends(optional_oauth2_scheme),
    redis: Redis = Depends(get_redis),
) -> None:
    # Bearer-style on the refresh token: possession of a valid refresh token
    # proves identity, so we don't require a live access token. Otherwise users
    # whose access token expired would have no way to revoke their session.

    # Best-effort: revoke the access token if one was supplied and parseable.
    if token:
        try:
            access_payload = decode_token(token)
            access_jti = access_payload.get("jti")
            access_exp_ts = access_payload.get("exp")
            if access_jti and access_exp_ts:
                access_exp = datetime.fromtimestamp(access_exp_ts, tz=timezone.utc)
                await blacklist_token(access_jti, access_exp, redis)
        except JWTError:
            pass  # Expired or malformed — nothing to revoke.

    # Authoritative: revoke the refresh token.
    try:
        refresh_payload = decode_token(body.refresh_token)
        if refresh_payload.get("type") != "refresh":
            return
        refresh_jti = refresh_payload.get("jti")
        refresh_exp_ts = refresh_payload.get("exp")
        if refresh_jti and refresh_exp_ts:
            refresh_exp = datetime.fromtimestamp(refresh_exp_ts, tz=timezone.utc)
            await blacklist_token(refresh_jti, refresh_exp, redis)
            logger.info("user_logged_out", user_id=refresh_payload.get("sub"))
    except JWTError:
        # Malformed/expired — nothing to revoke. Logout stays idempotent.
        return


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
@limiter.limit("10/minute")
async def update_me(
    request: Request,
    body: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return current_user
    repo = UserRepository(db)
    updated = await repo.update(current_user, **patch)
    logger.info("user_profile_updated", user_id=str(current_user.id), fields=list(patch.keys()))
    return updated


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Re-verify the current password before letting the user change it. Without
    # this, a stolen access token could lock the legitimate owner out by
    # rotating the password — the existing session itself isn't proof of intent.
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )
    current_user.hashed_password = get_password_hash(body.new_password)
    await db.commit()
    logger.info("user_password_changed", user_id=str(current_user.id))
