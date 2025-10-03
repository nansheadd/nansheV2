# Fichier: nanshe/backend/app/core/config.py (CORRIGÉ)
from pydantic_settings import BaseSettings
from typing import Optional, List, Union
from pydantic import AnyHttpUrl, ValidationError, field_validator
import sys

class Settings(BaseSettings):
    DATABASE_URL: str
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
    BACKEND_CORS_ORIGIN_REGEXES: List[str] = []
    RESEND_API_KEY: str

    FRONTEND_BASE_URL: AnyHttpUrl
    BACKEND_BASE_URL: AnyHttpUrl
    EMAIL_CONFIRM_TTL_H: int = 48
    EMAIL_RESET_TTL_MIN: int = 30
    RESEND_WEBHOOK_SECRET: str | None = None

    # --- Auth configuration ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Supabase Vector Store configuration ---
    SUPABASE_URL: AnyHttpUrl | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_VECTOR_TABLE: str = "vector_store"
    SUPABASE_VECTOR_SCHEMA: str = "public"
    SUPABASE_VECTOR_SOURCE_FILE: str = "app/data/training_data.jsonl"
    SUPABASE_VECTOR_ON_CONFLICT: str = "chunk_text"
    SUPABASE_VECTOR_BATCH_SIZE: int = 64
    SUPABASE_VECTOR_SYNC_ON_STARTUP: bool = True

    # Performance instrumentation
    SQLALCHEMY_SLOW_QUERY_THRESHOLD_MS: int = 300
    REQUEST_SLOW_THRESHOLD_MS: int = 400

    # Classification configuration
    DB_CLASSIFIER_DEFAULT_THRESHOLD: float = 0.2


    MAIL_PROVIDER: str = "resend"  # "sendgrid" | "brevo_smtp" | "resend"
    EMAIL_FROM: str

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
    SECRET_KEY: str

    # Configuration des embeddings
    USE_REMOTE_EMBEDDINGS: bool = False
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 384

    # Coach IA energy configuration
    COACH_ENERGY_MAX: int = 15
    COACH_ENERGY_RECOVERY_MINUTES: int = 24 * 60  # full refill over 24 hours by default
    COACH_ENERGY_MESSAGE_COST: float = 1.0

    class Config:
        env_file = ".env"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Ensure Postgres URLs always use the asyncpg driver.

        Vercel and many managed Postgres providers still expose database URLs
        using the legacy ``postgres://`` scheme. SQLAlchemy no longer ships the
        ``postgres`` alias, which triggers ``NoSuchModuleError`` when the API is
        imported on Vercel. We transparently upgrade those URLs – as well as
        ``postgresql://`` and psycopg variants – to ``postgresql+asyncpg://`` so
        the async engine boots correctly while keeping SQLite and other backends
        untouched.
        """

        if not isinstance(value, str):
            return value

        if "+asyncpg" in value:
            return value

        replacements = {
            "postgres://": "postgresql+asyncpg://",
            "postgresql://": "postgresql+asyncpg://",
            "postgresql+psycopg2://": "postgresql+asyncpg://",
            "postgresql+psycopg://": "postgresql+asyncpg://",
        }

        for prefix, target in replacements.items():
            if value.startswith(prefix):
                return target + value[len(prefix) :]

        return value

def _log_settings_validation_error(exc: ValidationError) -> None:
    """Pretty-print missing or invalid environment variables.

    When the Settings model fails to instantiate (for example on Vercel when a
    variable is missing), Pydantic raises a ValidationError.  Because the
    exception bubbles up during module import it can be tricky to spot which
    variable is responsible.  We explicitly log the structured error payload so
    the information shows up in server logs before re-raising the exception.
    """

    header = "Configuration error while loading environment variables:"
    print(header, file=sys.stderr)

    try:
        details = exc.errors()
    except Exception:  # pragma: no cover - extremely defensive
        details = None

    if details:
        for error in details:
            location = ".".join(str(part) for part in error.get("loc", ()))
            message = error.get("msg", "Unknown validation error")
            type_name = error.get("type")
            hint_parts = [message]
            if type_name:
                hint_parts.append(f"(type={type_name})")
            hint = " ".join(hint_parts)
            print(f"  - {location}: {hint}", file=sys.stderr)
    else:
        print(exc, file=sys.stderr)


try:
    settings = Settings()
except ValidationError as exc:  # pragma: no cover - exercised at runtime
    _log_settings_validation_error(exc)
    raise
