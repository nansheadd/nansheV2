from app.core.config import Settings


def build_settings(database_url: str) -> Settings:
    return Settings(
        DATABASE_URL=database_url,
        RESEND_API_KEY="dummy",
        FRONTEND_BASE_URL="http://frontend.test",
        BACKEND_BASE_URL="http://backend.test",
        EMAIL_FROM="robot@example.com",
        SECRET_KEY="super-secret",
    )


def test_postgres_scheme_is_upgraded():
    settings = build_settings("postgres://user:pass@db.example.com:5432/app")
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_postgresql_scheme_is_upgraded():
    settings = build_settings("postgresql://user:pass@db.example.com:5432/app")
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_psycopg_scheme_is_upgraded():
    settings = build_settings("postgresql+psycopg2://user:pass@db.example.com:5432/app")
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_asyncpg_scheme_is_preserved():
    settings = build_settings("postgresql+asyncpg://user:pass@db.example.com:5432/app")
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@db.example.com:5432/app"
