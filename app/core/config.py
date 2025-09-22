# Fichier: nanshe/backend/app/core/config.py (CORRIGÉ)
from __future__ import annotations

import logging
import secrets
from typing import List, Optional

from pydantic import AliasChoices, AnyHttpUrl, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _default_secret_key() -> str:
    """Génère une clé secrète éphémère utilisée lorsque la configuration est incomplète."""

    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./nanshe.db",
        validation_alias=AliasChoices(
            "DATABASE_URL",
            "POSTGRES_URL",
            "POSTGRES_PRISMA_URL",
            "POSTGRES_URL_NO_SSL",
            "SUPABASE_DB_URL",
        ),
    )
    GOOGLE_API_KEY: Optional[str] = None
    LOCAL_LLM_URL: Optional[str] = None
    REPLICATE_API_TOKEN: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_PREMIUM_PRICE_ID: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "https://nanshefr-v2.vercel.app",
    ]
    RESEND_API_KEY: str = Field(default="test-resend")

    FRONTEND_BASE_URL: AnyHttpUrl = Field(default="http://localhost:5173")
    BACKEND_BASE_URL: AnyHttpUrl = Field(default="http://localhost:8000")
    EMAIL_CONFIRM_TTL_H: int = 48
    EMAIL_RESET_TTL_MIN: int = 30
    RESEND_WEBHOOK_SECRET: str | None = None

    MAIL_PROVIDER: str = "resend"  # "sendgrid" | "brevo_smtp" | "resend"
    EMAIL_FROM: str = Field(default="noreply@example.com")

    # SendGrid
    SENDGRID_API_KEY: Optional[str] = None

    # Brevo SMTP
    BREVO_SMTP_HOST: str = "smtp-relay.brevo.com"
    BREVO_SMTP_PORT: int = 587
    BREVO_SMTP_USER: Optional[str] = None
    BREVO_SMTP_PASSWORD: Optional[str] = None

    ENVIRONMENT: str = "development"

    # --- NOUVELLE LIGNE ---
    # La clé secrète pour signer les JWTs.
    SECRET_KEY: str = Field(default_factory=_default_secret_key)

    # Configuration des embeddings
    USE_REMOTE_EMBEDDINGS: bool = False
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 384

    # Coach IA energy configuration
    COACH_ENERGY_MAX: int = 15
    COACH_ENERGY_RECOVERY_MINUTES: int = 24 * 60  # full refill over 24 hours by default
    COACH_ENERGY_MESSAGE_COST: float = 1.0

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://") and "+asyncpg" not in value:
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def _warn_on_defaults(self) -> "Settings":
        if "DATABASE_URL" not in self.model_fields_set and self.DATABASE_URL.startswith("sqlite"):
            logger.warning(
                "DATABASE_URL manquant : utilisation d'une base SQLite locale, non recommandée en production."
            )
        if "RESEND_API_KEY" not in self.model_fields_set or self.RESEND_API_KEY == "test-resend":
            logger.warning(
                "RESEND_API_KEY manquant : l'envoi d'e-mails transactionnels sera désactivé."
            )
        if "EMAIL_FROM" not in self.model_fields_set:
            logger.warning(
                "EMAIL_FROM non défini : utilisation de l'expéditeur par défaut %s.", self.EMAIL_FROM
            )
        if "SECRET_KEY" not in self.model_fields_set:
            logger.warning(
                "SECRET_KEY non défini : génération d'une clé éphémère, pensez à la définir pour les sessions."
            )
        return self


settings = Settings()
