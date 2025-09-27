"""Database session and engine utilities.

This module centralises the creation of both asynchronous and synchronous
SQLAlchemy engines.  It also offers a lightweight SQLite fallback for local
development when a PostgreSQL instance is unavailable.
"""

from __future__ import annotations

import logging
import os
import ssl
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)


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
    """Strip unsupported query params from asyncpg URLs."""

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


def _derive_sync_connection_parameters(async_url: str) -> tuple[str, dict[str, Any]]:
    """Return a synchronous SQLAlchemy URL matching the async configuration."""

    try:
        parsed_url: URL = make_url(async_url)
    except Exception:
        return async_url.replace("+asyncpg", ""), {}

    drivername = parsed_url.drivername
    connect_args: dict[str, Any] = {}

    if drivername.startswith("postgresql+"):
        # ``postgresql+asyncpg`` -> ``postgresql`` so psycopg can be used for sync work.
        parsed_url = parsed_url.set(drivername=drivername.split("+", 1)[0])
    elif drivername == "sqlite+aiosqlite":
        # Swap to the synchronous SQLite driver.
        parsed_url = parsed_url.set(drivername="sqlite")
        connect_args["check_same_thread"] = False

    return parsed_url.render_as_string(hide_password=False), connect_args


def _should_enable_sqlite_fallback() -> bool:
    environment = (getattr(settings, "ENVIRONMENT", "development") or "").lower()
    if os.getenv("DISABLE_SQLITE_FALLBACK") == "1":
        return False
    return environment in {"development", "local"}


SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///./nanshe_local.db"

# These globals are populated by ``configure_database``.
async_engine: AsyncEngine
sync_engine: Engine
SessionLocal: sessionmaker


def configure_database(database_url: str | None = None, *, allow_fallback: bool = True) -> None:
    """Initialise the engines and session factory.

    ``database_url`` defaults to the environment configuration.  When the
    connection attempt fails locally we transparently fall back to a SQLite
    database so the API can boot without a running PostgreSQL instance.
    """

    global async_engine, sync_engine, SessionLocal

    target_url = str(database_url or settings.DATABASE_URL)
    async_url, async_connect_args = _prepare_asyncpg_connection(target_url)

    logger.info("Configuration de la base de données: %s", async_url)

    candidate_async_engine = create_async_engine(
        async_url,
        echo=False,
        future=True,
        connect_args=async_connect_args,
    )

    sync_url, sync_connect_args = _derive_sync_connection_parameters(async_url)
    candidate_sync_engine = create_engine(
        sync_url,
        pool_pre_ping=True,
        connect_args=sync_connect_args,
    )

    # Verify the connection eagerly so we can provide a clearer error and/or
    # transparently switch to SQLite before the rest of the application boots.
    try:
        if candidate_sync_engine.dialect.name != "sqlite":
            with candidate_sync_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
    except (OperationalError, OSError) as exc:
        if allow_fallback and _should_enable_sqlite_fallback():
            logger.warning(
                "Impossible de joindre la base de données '%s' (%s). Bascule automatique vers SQLite.",
                async_url,
                exc,
            )
            # Dispose early to avoid keeping faulty connections around.
            try:
                candidate_sync_engine.dispose()
            except Exception:  # pragma: no cover - defensive cleanup
                pass
            try:
                candidate_async_engine.sync_engine.dispose()
            except Exception:  # pragma: no cover - defensive cleanup
                pass

            configure_database(SQLITE_FALLBACK_URL, allow_fallback=False)
            return

        logger.error("Connexion à la base de données échouée: %s", exc)
        raise

    async_engine = candidate_async_engine
    sync_engine = candidate_sync_engine
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


# Initialise the engines at import time so the rest of the application can use
# them immediately.
configure_database()


# Dépendance FastAPI pour les sessions synchrones (utilisée par vos routeurs API)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
