import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.db.models.user import AccountTokenPurpose
from app.services.account_service import request_password_reset, reset_password, verify_email

MODULE = "app.services.account_service"


class TestAccountService:
    async def test_verify_email_marks_user_verified_and_consumes_token(self, mock_db):
        user = MagicMock()
        user.id = uuid.uuid4()
        user.is_active = True
        user.is_email_verified = False
        token_row = MagicMock()
        token_row.user_id = user.id

        with (
            patch(f"{MODULE}.AccountTokenRepository") as MockTokenRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
        ):
            MockTokenRepo.return_value.get_active = AsyncMock(return_value=token_row)
            MockTokenRepo.return_value.mark_used = AsyncMock(return_value=token_row)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=user)

            result = await verify_email(mock_db, "raw-token")

        assert result is user
        assert user.is_email_verified is True
        MockTokenRepo.return_value.get_active.assert_awaited_once()
        assert MockTokenRepo.return_value.get_active.await_args.args[1] == AccountTokenPurpose.EMAIL_VERIFICATION
        MockTokenRepo.return_value.mark_used.assert_awaited_once_with(token_row)
        mock_db.commit.assert_awaited_once()

    async def test_verify_email_rejects_invalid_or_used_token(self, mock_db):
        with patch(f"{MODULE}.AccountTokenRepository") as MockTokenRepo:
            MockTokenRepo.return_value.get_active = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc:
                await verify_email(mock_db, "bad-token")

        assert exc.value.status_code == 400

    async def test_password_reset_updates_password_and_consumes_token(self, mock_db):
        user = MagicMock()
        user.id = uuid.uuid4()
        user.is_active = True
        user.hashed_password = "old"
        token_row = MagicMock()
        token_row.user_id = user.id

        with (
            patch(f"{MODULE}.AccountTokenRepository") as MockTokenRepo,
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
        ):
            MockTokenRepo.return_value.get_active = AsyncMock(return_value=token_row)
            MockTokenRepo.return_value.mark_used = AsyncMock(return_value=token_row)
            MockUserRepo.return_value.get_by_id = AsyncMock(return_value=user)

            await reset_password(mock_db, "raw-token", "newPassword123")

        assert user.hashed_password != "old"
        MockTokenRepo.return_value.get_active.assert_awaited_once()
        assert MockTokenRepo.return_value.get_active.await_args.args[1] == AccountTokenPurpose.PASSWORD_RESET
        MockTokenRepo.return_value.mark_used.assert_awaited_once_with(token_row)
        mock_db.commit.assert_awaited_once()

    async def test_password_reset_does_not_reveal_unknown_email(self, mock_db):
        with (
            patch(f"{MODULE}.UserRepository") as MockUserRepo,
            patch(f"{MODULE}.notify_password_reset", new_callable=AsyncMock) as notify,
        ):
            MockUserRepo.return_value.get_by_email = AsyncMock(return_value=None)

            await request_password_reset(mock_db, "missing@example.com")

        notify.assert_not_awaited()
