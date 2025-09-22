# Fichier: backend/app/db/session.py (VERSION FINALE)
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _build_sync_url(url: str) -> tuple[str, dict[str, object]]:
    """Convertit l'URL de connexion async en équivalent synchrone."""

    connect_args: dict[str, object] = {}
    if url.startswith("sqlite+aiosqlite"):
        sync_url = url.replace("+aiosqlite", "", 1)
        connect_args["check_same_thread"] = False
        return sync_url, connect_args
    if url.startswith("postgresql+asyncpg"):
        return url.replace("+asyncpg", "", 1), connect_args
    return url, connect_args


# --- Moteur Asynchrone (pour SQLAdmin) ---
# Lit l'URL complète "postgresql+asyncpg://..." de votre .env
database_url = str(settings.DATABASE_URL)
async_engine = create_async_engine(
    database_url,
    echo=False,
    future=True,
)


# --- Moteur Synchrone (pour votre API existante) ---
sync_db_url, connect_args = _build_sync_url(database_url)
sync_engine = create_engine(
    sync_db_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)


# Fabrique de sessions pour votre API (synchrone)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


# Dépendance FastAPI pour les sessions synchrones (utilisée par vos routeurs API)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
