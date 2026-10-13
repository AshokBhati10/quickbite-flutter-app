"""Central application configuration with fail-fast startup validation.

Every required setting is validated at import/startup time: missing values,
malformed URLs, weak JWT secrets, bad CORS origins, negative delays, and an
inconsistent retry policy all raise before the app starts serving.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    SYNC_DATABASE_URL: str
    AMQP_URL: str

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    CORS_ORIGINS: str = "http://localhost:3000"

    PAYMENT_DELAY_S: float = 0.2
    RESTAURANT_DELAY_S: float = 0.2
    DELIVERY_DELAY_S: float = 0.2
    NOTIFICATION_DELAY_S: float = 0.1

    PAYMENT_MODE: str = "ok"
    RESTAURANT_MODE: str = "ok"
    DELIVERY_MODE: str = "ok"
    NOTIFICATION_MODE: str = "ok"

    RETRY_MAX_RETRIES: int = 3
    RETRY_DELAYS_S: str = "2,10,30"

    @field_validator("DATABASE_URL", "SYNC_DATABASE_URL")
    @classmethod
    def _must_be_postgres(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a postgresql URL")
        return v

    @field_validator("AMQP_URL")
    @classmethod
    def _must_be_amqp(cls, v: str) -> str:
        if not v.startswith("amqp"):
            raise ValueError("AMQP_URL must be an amqp URL")
        return v

    @field_validator("JWT_SECRET")
    @classmethod
    def _secret_must_be_real(cls, v: str) -> str:
        if not v or v.startswith("change-me"):
            raise ValueError("JWT_SECRET must be set to a real secret")
        if len(v) < 16:
            raise ValueError("JWT_SECRET must be at least 16 characters")
        return v

    @field_validator("JWT_EXPIRE_MINUTES")
    @classmethod
    def _expiry_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("JWT_EXPIRE_MINUTES must be positive")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _origins_explicit(cls, v: str) -> str:
        origins = [o.strip() for o in v.split(",") if o.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must list at least one origin")
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must not contain a wildcard")
        return ",".join(origins)

    @field_validator(
        "PAYMENT_DELAY_S",
        "RESTAURANT_DELAY_S",
        "DELIVERY_DELAY_S",
        "NOTIFICATION_DELAY_S",
    )
    @classmethod
    def _delays_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("simulated delays must be >= 0")
        return v

    @field_validator("PAYMENT_MODE")
    @classmethod
    def _payment_mode_known(cls, v: str) -> str:
        allowed = {
            "ok",
            "fail-twice-then-succeed",
            "always-fail",
            "crash-before-commit",
            "crash-after-commit-before-ack",
        }
        if v not in allowed:
            raise ValueError(f"PAYMENT_MODE must be one of {sorted(allowed)}")
        return v

    @field_validator("RESTAURANT_MODE", "DELIVERY_MODE")
    @classmethod
    def _stage_mode_known(cls, v: str) -> str:
        if v not in {"ok", "fail"}:
            raise ValueError("stage mode must be 'ok' or 'fail'")
        return v

    @field_validator("NOTIFICATION_MODE")
    @classmethod
    def _notification_mode_known(cls, v: str) -> str:
        if v not in {"ok", "fail"}:
            raise ValueError("NOTIFICATION_MODE must be 'ok' or 'fail'")
        return v

    def retry_delays(self) -> list[float]:
        try:
            delays = [float(x.strip()) for x in self.RETRY_DELAYS_S.split(",")]
        except ValueError as exc:
            raise ValueError("RETRY_DELAYS_S must be comma-separated numbers") from exc
        if len(delays) != self.RETRY_MAX_RETRIES:
            raise ValueError(
                "RETRY_DELAYS_S must have exactly RETRY_MAX_RETRIES entries"
            )
        if any(d < 0 for d in delays):
            raise ValueError("retry delays must be >= 0")
        return delays

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
