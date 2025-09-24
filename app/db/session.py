# Fichier: backend/app/db/session.py (VERSION FINALE)
from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _prepare_asyncpg_connection(url: str) -> tuple[str, dict]:
    """Strip unsupported query params from asyncpg URLs.

    Providers such as Supabase append ``sslmode=require`` to their connection
    strings.  SQLAlchemy propagates any query parameter to ``asyncpg.connect``
    which does not understand the ``sslmode`` keyword and raises
    ``TypeError: connect() got an unexpected keyword argument 'sslmode'``.

    We remove this parameter for the async engine while keeping it on the
    original URL (used by the synchronous psycopg engine where ``sslmode`` is
    valid) and translate common ``sslmode`` values to the boolean ``ssl`` flag
    expected by asyncpg.
    """

    try:
        parsed_url = make_url(url)
    except Exception:
        return url, {}

    if not parsed_url.drivername.startswith("postgresql+asyncpg"):
        return url, {}

    query = dict(parsed_url.query)
    sslmode = query.pop("sslmode", None)

    connect_args: dict[str, object] = {}
    if isinstance(sslmode, str):
        sslmode_normalized = sslmode.lower()
        ssl_mapping = {
            "disable": False,
            "allow": True,
            "prefer": True,
            "require": True,
            "verify-ca": True,
            "verify-full": True,
        }
        if sslmode_normalized in ssl_mapping:
            connect_args["ssl"] = ssl_mapping[sslmode_normalized]

    sanitized_url = parsed_url.set(query=query).render_as_string(hide_password=False)
    return sanitized_url, connect_args

# --- Moteur Asynchrone (pour SQLAdmin) ---
# Lit l'URL complète "postgresql+asyncpg://..." de votre .env
_async_url, _async_connect_args = _prepare_asyncpg_connection(str(settings.DATABASE_URL))

async_engine = create_async_engine(
    _async_url,
    echo=False,
    future=True,
    connect_args=_async_connect_args,
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
