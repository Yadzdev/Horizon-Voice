"""Small environment configuration without requiring a .env parser at import time."""
from dataclasses import dataclass
import os
from pathlib import Path


def _read_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_read_dotenv(Path.cwd() / ".env")
_read_dotenv(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Horizon Voice API")
    environment: str = os.getenv("ENVIRONMENT", "development")
    api_prefix: str = "/api/v1"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./horizon_voice.db")
    jwt_secret: str = os.getenv("JWT_SECRET", "development-only-change-me")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "horizon-voice")
    access_token_minutes: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
    browser_session_minutes: int = int(os.getenv("BROWSER_SESSION_MINUTES", str(60 * 12)))
    pairing_code_seconds: int = int(os.getenv("PAIRING_CODE_SECONDS", "180"))
    pairing_rate_per_minute: int = int(os.getenv("PAIRING_RATE_PER_MINUTE", "5"))
    public_base_domain: str = os.getenv("PUBLIC_BASE_DOMAIN", "voice-horizon.online")
    livekit_url: str = os.getenv("LIVEKIT_URL", "http://livekit:7880")
    livekit_public_url: str = os.getenv("LIVEKIT_PUBLIC_URL", "wss://media.voice-horizon.online")
    livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "")
    livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "")
    livekit_token_minutes: int = int(os.getenv("LIVEKIT_TOKEN_MINUTES", "60"))
    livekit_room_max_participants: int = int(os.getenv("LIVEKIT_ROOM_MAX_PARTICIPANTS", "500"))
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    auto_create_schema: bool = os.getenv("AUTO_CREATE_SCHEMA", "true").lower() == "true"
    default_proximity_blocks: float = float(os.getenv("DEFAULT_PROXIMITY_BLOCKS", "30"))

    def __post_init__(self) -> None:
        if self.environment.lower() == "production":
            if len(self.jwt_secret) < 64 or "CHANGE_ME" in self.jwt_secret or self.jwt_secret == "development-only-change-me":
                raise RuntimeError("JWT_SECRET must be a unique random value of at least 64 characters in production")
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise RuntimeError("Production deployments must use PostgreSQL, not SQLite")
            if not self.cookie_secure:
                raise RuntimeError("COOKIE_SECURE must be true in production")
            if not self.livekit_api_key or not self.livekit_api_secret:
                raise RuntimeError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be configured in production")
            if self.auto_create_schema:
                raise RuntimeError("AUTO_CREATE_SCHEMA must be false in production; use Alembic migrations")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
