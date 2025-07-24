# Fichier: nanshe/backend/app/core/config.py (MIS À JOUR)
from pydantic_settings import BaseSettings
from typing import Optional, List, Union

class Settings(BaseSettings):
    DATABASE_URL: str
    GOOGLE_API_KEY: Optional[str] = None

    # --- NOUVELLE LIGNE ---
    # On définit une variable pour nos origines CORS.
    # Elle attendra une liste de chaînes de caractères.
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"

settings = Settings()