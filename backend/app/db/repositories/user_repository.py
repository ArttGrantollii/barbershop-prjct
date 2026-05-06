from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User, UserRole
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        email: str,
        hashed_password: str,
        role: UserRole = UserRole.CUSTOMER,
        phone: str | None = None,
    ) -> User:
        user = User(
            name=name,
            email=email,
            phone=phone,
            hashed_password=hashed_password,
            role=role,
        )
        return await self.save(user)

    async def update(self, user: User, **kwargs) -> User:
        for key, value in kwargs.items():
            setattr(user, key, value)
        return await self.save(user)
