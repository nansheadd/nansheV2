# Fichier: nanshe/backend/app/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    GOOGLE_API_KEY: Optional[str] = None # On l'ajoute ici


    class Config:
        env_file = ".env"

settings = Settings()