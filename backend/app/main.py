from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging_config import configure_logging
from app.db.redis import close_redis
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(debug=settings.DEBUG)
    await _bootstrap_admin()
    await _seed_business_hours()
    await _seed_services()
    yield
    await close_redis()
    await engine.dispose()


async def _bootstrap_admin() -> None:
    if not settings.FIRST_ADMIN_EMAIL or not settings.FIRST_ADMIN_PASSWORD:
        return
    from app.core.security import get_password_hash
    from app.db.models.user import UserRole
    from app.db.repositories.user_repository import UserRepository
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        if await repo.get_by_email(settings.FIRST_ADMIN_EMAIL):
            return
        await repo.create(
            name="Admin",
            email=settings.FIRST_ADMIN_EMAIL,
            hashed_password=get_password_hash(settings.FIRST_ADMIN_PASSWORD),
            role=UserRole.ADMIN,
        )


async def _seed_business_hours() -> None:
    import datetime
    from app.db.repositories.business_repository import BusinessRepository
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        repo = BusinessRepository(db)
        if await repo.get_all_hours():
            return
        for day in range(7):
            await repo.upsert_hours(
                day_of_week=day,
                open_time=datetime.time(9, 0),
                close_time=datetime.time(18, 0),
                is_closed=(day == 6),
            )


async def _seed_services() -> None:
    from decimal import Decimal
    from app.db.repositories.service_repository import ServiceRepository
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        repo = ServiceRepository(db)
        if await repo.get_all():
            return
        await repo.create("Haircut", "Classic haircut", 30, Decimal("25.00"))
        await repo.create("Haircut & Beard", "Haircut with beard trim", 45, Decimal("35.00"))
        await repo.create("Female Cut & Style", "Cut and blow-dry", 60, Decimal("50.00"))


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "healthy", "service": settings.PROJECT_NAME}
