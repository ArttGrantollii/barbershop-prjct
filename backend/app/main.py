import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging_config import configure_logging
from app.db.redis import close_redis, get_redis
from app.db.session import engine
from app.workers.reminders import start_reminder_loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(debug=settings.DEBUG)
    reminder_task = start_reminder_loop()
    try:
        yield
    finally:
        # Cancel the reminder loop and wait for it to finish so we don't
        # leave a half-completed iteration hanging during shutdown.
        if reminder_task is not None:
            reminder_task.cancel()
            try:
                await reminder_task
            except (asyncio.CancelledError, Exception):
                pass
        await close_redis()
        await engine.dispose()

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


@app.get("/ready", tags=["health"])
async def readiness():
    checks = {"database": "unknown", "redis": "unknown"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"

        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": settings.PROJECT_NAME,
                "checks": checks,
                "error": exc.__class__.__name__,
            },
        )
    return {"status": "ready", "service": settings.PROJECT_NAME, "checks": checks}
