# Fichier: nanshe/backend/app/core/config.py (CORRIGÉ)
from pydantic_settings import BaseSettings
from typing import Optional, List, Union
from pydantic import AnyHttpUrl

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
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:8000","http://127.0.0.1:5173"]
    RESEND_API_KEY: str

    FRONTEND_BASE_URL: AnyHttpUrl
    BACKEND_BASE_URL: AnyHttpUrl
    EMAIL_CONFIRM_TTL_H: int = 48
    EMAIL_RESET_TTL_MIN: int = 30
    RESEND_WEBHOOK_SECRET: str | None = None


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

    class Config:
        env_file = ".env"

settings = Settings()