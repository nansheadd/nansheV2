import sys
from importlib import import_module, reload
from types import ModuleType

import pytest


@pytest.fixture(autouse=True)
def _cleanup_session_module():
    yield
    sys.modules.pop("app.db.session", None)


def _reload_session_module() -> ModuleType:
    # ``configure_database`` runs at import time, so reloading the module allows
    # us to exercise the different code paths by tweaking environment variables.
    session_module = import_module("app.db.session")
    return reload(session_module)


def test_sqlite_sync_parameters(tmp_path, monkeypatch):
    database_path = tmp_path / "local.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DISABLE_SQLITE_FALLBACK", raising=False)

    session_module = _reload_session_module()

    assert session_module.sync_engine.url.drivername == "sqlite"
    assert session_module.sync_engine.url.database.endswith("local.db")


def test_postgres_connection_error_triggers_sqlite_fallback(monkeypatch):
    # Point the configuration at a non-existent PostgreSQL port so the
    # connection check fails instantly.  The fallback should switch to the
    # bundled SQLite database.
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@127.0.0.1:65000/app")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("DISABLE_SQLITE_FALLBACK", raising=False)

    session_module = _reload_session_module()

    assert session_module.async_engine.url.drivername == "sqlite+aiosqlite"
