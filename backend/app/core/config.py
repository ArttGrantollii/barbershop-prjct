from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Vendos Salon"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Required — no default. Generate with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    EMAIL_VERIFICATION_TOKEN_HOURS: int = 24
    PASSWORD_RESET_TOKEN_MINUTES: int = 30

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"

    ALLOWED_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"

    NOTIFICATIONS_BACKEND: str = "console"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_SES_FROM_EMAIL: str = ""
    AWS_SNS_SENDER_ID: str = "VendosSalon"

    # IANA timezone name for the salon's physical location.
    # Business hours are interpreted in this timezone; set it to match where the
    # salon actually is (e.g. "America/New_York", "Europe/London").
    SALON_TIMEZONE: str = "UTC"

    SLOT_HOLD_TTL_SECONDS: int = 600
    CANCELLATION_WINDOW_HOURS: int = 2
    CANCELLATION_LIMIT_PER_DAY: int = 3
    SLOT_COOLDOWN_SECONDS: int = 1800  # 30 minutes
    # Minimum advance notice required for new bookings, in minutes. Set to 0
    # to allow last-minute bookings up to "now". Filters slots in the grid and
    # also rejects holds/bookings that fall inside the window — defense in
    # depth in case a stale grid lets a too-soon slot through.
    MIN_LEAD_MINUTES: int = 0
    # 24h reminder worker. Disable for unit tests / one-shot CLI runs.
    # Lookahead and tolerance combine to match bookings whose start_time is
    # roughly 24h away (24h ± REMINDER_TOLERANCE_MINUTES).
    REMINDERS_ENABLED: bool = True
    REMINDER_LEAD_HOURS: int = 24
    REMINDER_TOLERANCE_MINUTES: int = 60
    REMINDER_INTERVAL_SECONDS: int = 300  # 5 minutes

    FIRST_ADMIN_EMAIL: str = ""
    FIRST_ADMIN_PASSWORD: str = ""

    @model_validator(mode="after")
    def _validate_secrets(self) -> "Settings":
        if len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters. "
                'Generate one: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()
