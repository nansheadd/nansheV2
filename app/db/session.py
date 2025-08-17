# Fichier: backend/app/db/session.py (VERSION FINALE)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# --- Moteur Asynchrone (pour SQLAdmin) ---
# Lit l'URL complète "postgresql+asyncpg://..." de votre .env
async_engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=False,
    future=True,
)

# --- Moteur Synchrone (pour votre API existante) ---
# On retire "+asyncpg" pour que SQLAlchemy utilise le pilote synchrone par défaut (psycopg2)
sync_db_url = str(settings.DATABASE_URL).replace("+asyncpg", "")
sync_engine = create_engine(
    sync_db_url,
    pool_pre_ping=True
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