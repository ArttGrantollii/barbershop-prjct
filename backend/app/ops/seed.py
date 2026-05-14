from __future__ import annotations

import argparse
import asyncio
from datetime import time
from decimal import Decimal

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models.user import UserRole
from app.db.repositories.business_repository import BusinessRepository
from app.db.repositories.service_repository import ServiceRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import AsyncSessionLocal, engine


async def seed_admin() -> bool:
    if not settings.FIRST_ADMIN_EMAIL or not settings.FIRST_ADMIN_PASSWORD:
        return False

    async with AsyncSessionLocal() as db:
        repo = UserRepository(db)
        if await repo.get_by_email(settings.FIRST_ADMIN_EMAIL):
            return False
        await repo.create(
            name="Admin",
            email=settings.FIRST_ADMIN_EMAIL,
            hashed_password=get_password_hash(settings.FIRST_ADMIN_PASSWORD),
            role=UserRole.ADMIN,
        )
        return True


async def seed_business_hours() -> bool:
    async with AsyncSessionLocal() as db:
        repo = BusinessRepository(db)
        if await repo.get_all_hours():
            return False
        for day in range(7):
            await repo.upsert_hours(
                day_of_week=day,
                open_time=time(9, 0),
                close_time=time(18, 0),
                is_closed=(day == 6),
            )
        return True


async def seed_services() -> bool:
    async with AsyncSessionLocal() as db:
        repo = ServiceRepository(db)
        if await repo.get_all():
            return False
        await repo.create("Haircut", "Classic haircut", 30, Decimal("25.00"))
        await repo.create("Haircut & Beard", "Haircut with beard trim", 45, Decimal("35.00"))
        await repo.create("Female Cut & Style", "Cut and blow-dry", 60, Decimal("50.00"))
        return True


async def seed_all(*, include_admin: bool = True, include_defaults: bool = True) -> dict[str, bool]:
    results = {"admin": False, "business_hours": False, "services": False}
    if include_admin:
        results["admin"] = await seed_admin()
    if include_defaults:
        results["business_hours"] = await seed_business_hours()
        results["services"] = await seed_services()
    return results


async def _run(args: argparse.Namespace) -> int:
    try:
        results = await seed_all(
            include_admin=not args.skip_admin,
            include_defaults=not args.skip_defaults,
        )
        created = [name for name, did_create in results.items() if did_create]
        if created:
            print(f"Seeded: {', '.join(created)}")
        else:
            print("Seed complete: no changes needed")
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed initial Vendos Salon data.")
    parser.add_argument("--skip-admin", action="store_true", help="Do not create FIRST_ADMIN_EMAIL.")
    parser.add_argument("--skip-defaults", action="store_true", help="Do not create default hours/services.")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
