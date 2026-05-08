import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import AccountToken, AccountTokenPurpose
from app.db.repositories.base import BaseRepository


class AccountTokenRepository(BaseRepository[AccountToken]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(AccountToken, db)

    async def create_token(
        self,
        *,
        user_id: uuid.UUID,
        purpose: AccountTokenPurpose,
        token_hash: str,
        expires_at: datetime,
    ) -> AccountToken:
        return await self.save(
            AccountToken(
                user_id=user_id,
                purpose=purpose,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )

    async def get_active(self, token_hash: str, purpose: AccountTokenPurpose) -> AccountToken | None:
        result = await self.db.execute(
            select(AccountToken).where(
                AccountToken.token_hash == token_hash,
                AccountToken.purpose == purpose,
                AccountToken.used_at.is_(None),
                AccountToken.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalars().one_or_none()

    async def mark_used(self, token: AccountToken) -> AccountToken:
        token.used_at = datetime.now(timezone.utc)
        return await self.save(token)

    async def expire_user_tokens(self, user_id: uuid.UUID, purpose: AccountTokenPurpose) -> None:
        await self.db.execute(
            update(AccountToken)
            .where(
                AccountToken.user_id == user_id,
                AccountToken.purpose == purpose,
                AccountToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(timezone.utc))
        )
        await self.db.commit()
