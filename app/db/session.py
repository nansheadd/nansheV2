"""Database session and engine utilities.

This module centralises the creation of both asynchronous and synchronous
SQLAlchemy engines.  It also offers a lightweight SQLite fallback for local
development when a PostgreSQL instance is unavailable.
"""

from __future__ import annotations

import logging
import os
import ssl
import time
from time import perf_counter
from typing import Any, Optional

from sqlalchemy import create_engine, event, text
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


def _install_slow_query_logger(engine: Engine) -> None:
    """Attach callbacks that warn when queries exceed the configured budget."""

    threshold_ms = max(getattr(settings, "SQLALCHEMY_SLOW_QUERY_THRESHOLD_MS", 0) or 0, 0)
    if threshold_ms == 0:
        return

    marker = "_nanshe_slow_query_hook"
    if getattr(engine, marker, False):  # pragma: no cover - defensive guard
        return

    setattr(engine, marker, True)

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[override]
        context._nanshe_query_start = perf_counter()

    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[override]
        start = getattr(context, "_nanshe_query_start", None)
        if start is None:
            return

        elapsed_ms = (perf_counter() - start) * 1000.0
        if elapsed_ms < threshold_ms:
            return

        snippet = " ".join(statement.split()) if isinstance(statement, str) else str(statement)
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."

        try:
            params_preview = repr(parameters)
        except Exception:  # pragma: no cover - extremely defensive
            params_preview = "<unavailable>"

        if len(params_preview) > 200:
            params_preview = params_preview[:197] + "..."

        logger.warning(
            "SQL lente (%.1f ms) - %s | params=%s",
            elapsed_ms,
            snippet,
            params_preview,
        )

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    event.listen(engine, "after_cursor_execute", _after_cursor_execute)


def _verify_database_connection(engine: Engine) -> None:
    """Ping *engine* with retry logic to tolerate transient outages."""

    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return

    max_retries = max(int(getattr(settings, "DATABASE_CONNECTION_MAX_RETRIES", 1) or 1), 1)
    backoff = max(float(getattr(settings, "DATABASE_CONNECTION_RETRY_BACKOFF_SECONDS", 1.0) or 1.0), 0.1)

    attempt = 1
    last_exc: Optional[Exception] = None

    while attempt <= max_retries:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except (OperationalError, OSError) as exc:
            last_exc = exc
            if attempt >= max_retries:
                break

            delay = min(30.0, backoff * (2 ** (attempt - 1)))
            logger.warning(
                "Connexion à la base de données échouée (tentative %s/%s): %s. Nouvelle tentative dans %.1f s.",
                attempt,
                max_retries,
                exc,
                delay,
            )
            time.sleep(delay)
            attempt += 1

    if last_exc is not None:
        raise last_exc


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

    _install_slow_query_logger(candidate_sync_engine)
    try:
        _install_slow_query_logger(candidate_async_engine.sync_engine)
    except Exception:  # pragma: no cover - defensive
        logger.debug("Impossible d'installer le logger SQL sur le moteur async.")

    # Verify the connection eagerly so we can provide a clearer error and/or
    # transparently switch to SQLite before the rest of the application boots.
    try:
        _verify_database_connection(candidate_sync_engine)
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
