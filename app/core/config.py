# Fichier: nanshe/backend/app/core/config.py (CORRIGÉ)
from pydantic_settings import BaseSettings
from typing import Optional, List, Union

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
    
    ENVIRONMENT: str = "development"
    
    # --- NOUVELLE LIGNE ---
    # La clé secrète pour signer les JWTs.
    SECRET_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()