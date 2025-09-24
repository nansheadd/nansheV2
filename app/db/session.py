# Fichier: backend/app/db/session.py (VERSION FINALE)
from __future__ import annotations

import ssl

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _create_ssl_context(
    mode: str,
    root_cert: str | None,
    client_cert: str | None,
    client_key: str | None,
) -> ssl.SSLContext:
    """Create an :class:`ssl.SSLContext` matching libpq ``sslmode`` semantics."""

    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

    if root_cert:
        context.load_verify_locations(cafile=root_cert)

    if client_cert:
        context.load_cert_chain(certfile=client_cert, keyfile=client_key)

    if mode in {"verify-ca", "verify-full"}:
        context.check_hostname = mode == "verify-full"
    else:
        # ``require``/``prefer``/``allow`` should only ensure encryption, mirroring
        # libpq's behaviour where certificate validation is skipped.
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    return context


def _prepare_asyncpg_connection(url: str) -> tuple[str, dict[str, object]]:
    """Strip unsupported query params from asyncpg URLs.

    Providers such as Supabase append ``sslmode=require`` to their connection
    strings.  SQLAlchemy propagates any query parameter to ``asyncpg.connect``
    which does not understand the ``sslmode`` keyword and raises
    ``TypeError: connect() got an unexpected keyword argument 'sslmode'``.

    We remove this parameter for the async engine while keeping it on the
    original URL (used by the synchronous psycopg engine where ``sslmode`` is
    valid) and translate common ``sslmode`` values to an ``ssl`` argument that
    mirrors libpq's behaviour for ``asyncpg``.
    """

    try:
        parsed_url = make_url(url)
    except Exception:
        return url, {}

    if not parsed_url.drivername.startswith("postgresql+asyncpg"):
        return url, {}

    query = dict(parsed_url.query)
    sslmode = query.pop("sslmode", None)
    sslrootcert = query.pop("sslrootcert", None)
    sslcert = query.pop("sslcert", None)
    sslkey = query.pop("sslkey", None)

    connect_args: dict[str, object] = {}
    if isinstance(sslmode, str):
        sslmode_normalized = sslmode.lower()

        if sslmode_normalized == "disable":
            connect_args["ssl"] = False
        elif sslmode_normalized in {"allow", "prefer", "require", "verify-ca", "verify-full"}:
            connect_args["ssl"] = _create_ssl_context(
                sslmode_normalized,
                root_cert=sslrootcert,
                client_cert=sslcert,
                client_key=sslkey,
            )

    elif sslrootcert or sslcert:
        # libpq enables TLS implicitly when any certificate paths are provided.
        connect_args["ssl"] = _create_ssl_context(
            "require",
            root_cert=sslrootcert,
            client_cert=sslcert,
            client_key=sslkey,
        )

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
