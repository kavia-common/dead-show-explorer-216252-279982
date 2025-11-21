import logging
import os
from datetime import timedelta
from typing import List, Optional

from pydantic import AnyUrl, Field, PostgresDsn, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    This configuration centralizes environment-based settings for the FastAPI backend.
    It ensures secure defaults and avoids hardcoding sensitive data.

    Required environment variables:
    - DATABASE_URL: PostgreSQL DSN for the shows_database container.
    - JWT_SECRET: Secret key for signing JWT tokens.

    Optional environment variables:
    - JWT_EXPIRES_MINUTES: Token lifetime in minutes (default: 60).
    - CORS_ORIGINS: Comma-separated list of allowed CORS origins (default: *).
    - COOKIE_SECURE: Whether cookies require HTTPS (default: true).
    - COOKIE_DOMAIN: Domain scope for cookies (default: unset).
    - COOKIE_SAMESITE: SameSite policy: lax/strict/none (default: lax).
    - ENV: Runtime environment name (development/production/test).
    """

    # Core
    ENV: str = Field(default="development", description="Runtime environment")

    # Database
    DATABASE_URL: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL (e.g., postgres://user:pass@host:5432/dbname)",
    )

    # Auth
    JWT_SECRET: str = Field(..., min_length=16, description="JWT signing secret")
    JWT_EXPIRES_MINUTES: int = Field(
        default=60, ge=5, le=60 * 24 * 7, description="JWT expiry in minutes"
    )

    # CORS
    CORS_ORIGINS: Optional[str] = Field(
        default="*",
        description="Comma-separated origins for CORS. Use * for all (dev only).",
    )

    # Cookies
    COOKIE_SECURE: bool = Field(
        default=True, description="Set Secure flag on cookies (HTTPS only)"
    )
    COOKIE_DOMAIN: Optional[str] = Field(
        default=None, description="Domain for cookies (e.g., .example.com)"
    )
    COOKIE_SAMESITE: str = Field(
        default="lax",
        description="SameSite policy for cookies: lax, strict, none",
    )

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # PUBLIC_INTERFACE
    def cors_origins_list(self) -> List[str]:
        """Return parsed list of CORS origins. Supports wildcard '*' or CSV list."""
        raw = (self.CORS_ORIGINS or "").strip()
        if not raw:
            return []
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    # PUBLIC_INTERFACE
    def jwt_expiry(self) -> timedelta:
        """Return JWT expiration as timedelta."""
        return timedelta(minutes=int(self.JWT_EXPIRES_MINUTES))

    # PUBLIC_INTERFACE
    def cookie_samesite_normalized(self) -> str:
        """Return normalized SameSite value ensuring one of lax/strict/none."""
        value = (self.COOKIE_SAMESITE or "lax").lower()
        if value not in {"lax", "strict", "none"}:
            logger.warning("Invalid COOKIE_SAMESITE value '%s', falling back to 'lax'", value)
            return "lax"
        return value


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Load and return application settings with validation and safe logging."""
    try:
        settings = Settings()  # Loads from env and .env
        _log_settings_safely(settings)
        return settings
    except ValidationError as exc:
        # Avoid leaking secrets or internal paths
        logger.error("Configuration validation failed. Please verify required environment variables.")
        # Raise a generic error upwards; FastAPI startup can catch/log
        raise RuntimeError("Invalid configuration. Check environment variables.") from exc


def _log_settings_safely(settings: Settings) -> None:
    """
    Log non-sensitive settings at startup to aid diagnostics.
    Sensitive fields like JWT secrets are never logged.
    """
    try:
        safe = {
            "ENV": settings.ENV,
            "DATABASE_URL": _mask_dsn(settings.DATABASE_URL),
            "JWT_EXPIRES_MINUTES": settings.JWT_EXPIRES_MINUTES,
            "CORS_ORIGINS": settings.cors_origins_list(),
            "COOKIE_SECURE": settings.COOKIE_SECURE,
            "COOKIE_DOMAIN": settings.COOKIE_DOMAIN,
            "COOKIE_SAMESITE": settings.cookie_samesite_normalized(),
        }
        logger.info("App settings (safe): %s", safe)
    except Exception:
        # Never fail application due to logging issues
        logger.debug("Failed to log settings safely", exc_info=False)


def _mask_dsn(dsn: AnyUrl) -> str:
    """
    Return a masked DSN with credentials redacted.
    Example: postgres://****:****@host:5432/dbname
    """
    try:
        value = str(dsn)
        # Basic masking for user:pass@
        return value.replace("//", "//****:****@") if "@" in value else value
    except Exception:
        return "unavailable"
