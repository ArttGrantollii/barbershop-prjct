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

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"

    ALLOWED_ORIGINS: str = "http://localhost:3000"

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
