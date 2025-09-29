"""Reset the Supabase/Vercel PostgreSQL schema and reseed core data.

Usage examples::

    poetry run python -m scripts.reset_database --yes \
        --database-url postgresql+asyncpg://user:pass@host/db \
        --supabase-url https://xxx.supabase.co \
        --supabase-key YOUR_SERVICE_ROLE_KEY

    # Skip the seed phase (drops & recreates tables only)
    python backend/scripts/reset_database.py --yes --skip-seed

The script drops every table declared in the SQLAlchemy metadata, recreates the
schema (and ensures the ``pgvector`` extension exists) and optionally launches
the canonical seed routines (classifier examples, skills, badges, roadmaps).

**Warning**: This is destructive. Always verify you are targeting the correct
database before running in production.
"""

from __future__ import annotations

import argparse
import os
import sys
from importlib import reload
from pathlib import Path

# Ensure project root is on sys.path when executed as a module or script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from sqlalchemy import text

# Lazily-populated module references (updated in ``_apply_environment_overrides``).
from app.db import base as base_module
from app.db import session as session_module
from scripts import run_seeds as run_seeds_module

Base = base_module.Base
SessionLocal = session_module.SessionLocal
sync_engine = session_module.sync_engine
configure_database = session_module.configure_database
run_seeds = run_seeds_module


def _apply_environment_overrides(args: argparse.Namespace) -> None:
    """Apply Supabase/Database overrides and refresh app settings if required."""

    overrides_applied = False

    if args.supabase_url:
        os.environ["SUPABASE_URL"] = args.supabase_url
        overrides_applied = True
    if args.supabase_key:
        os.environ["SUPABASE_SERVICE_ROLE_KEY"] = args.supabase_key
        overrides_applied = True
    if args.supabase_table:
        os.environ["SUPABASE_VECTOR_TABLE"] = args.supabase_table
        overrides_applied = True
    if args.supabase_schema:
        os.environ["SUPABASE_VECTOR_SCHEMA"] = args.supabase_schema
        overrides_applied = True

    if overrides_applied or args.database_url:
        from app.core import config as config_module

        reload(config_module)
        session = reload(session_module)
        seeds = reload(run_seeds_module)

        global SessionLocal, sync_engine, configure_database, run_seeds

        SessionLocal = session.SessionLocal
        sync_engine = session.sync_engine
        configure_database = session.configure_database
        run_seeds = seeds


def ensure_pgvector_extension() -> None:
    """Create the pgvector extension when running against PostgreSQL."""

    if sync_engine.dialect.name != "postgresql":
        return

    with sync_engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.commit()


def reset_schema() -> None:
    """Drop all tables then recreate the schema from SQLAlchemy metadata."""

    # Dropping and recreating via metadata ensures the order respects FKs.
    Base.metadata.drop_all(bind=sync_engine, checkfirst=True)
    ensure_pgvector_extension()
    Base.metadata.create_all(bind=sync_engine)


def run_seed_pipeline() -> None:
    """Execute the standard seed routines used in run_seeds.py."""

    session = SessionLocal()
    try:
        system_user = run_seeds.get_or_create_default_user(session)
        run_seeds.seed_classifier_examples(session)
        run_seeds.seed_skills(session)
        run_seeds.seed_badges(session)
        run_seeds.seed_language_roadmaps(session, system_user)
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset and reseed the database")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm the destructive reset without an interactive prompt.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip the data seeding phase after recreating the schema.",
    )
    parser.add_argument(
        "--database-url",
        dest="database_url",
        default=None,
        help="Override settings.DATABASE_URL (useful for targeting another environment).",
    )
    parser.add_argument(
        "--supabase-url",
        dest="supabase_url",
        default=None,
        help="Supabase REST base URL to inject before seeding.",
    )
    parser.add_argument(
        "--supabase-key",
        dest="supabase_key",
        default=None,
        help="Supabase service role key to inject before seeding.",
    )
    parser.add_argument(
        "--supabase-table",
        dest="supabase_table",
        default=None,
        help="Override SUPABASE_VECTOR_TABLE for the seeding run.",
    )
    parser.add_argument(
        "--supabase-schema",
        dest="supabase_schema",
        default=None,
        help="Override SUPABASE_VECTOR_SCHEMA for the seeding run.",
    )
    args = parser.parse_args(argv)

    if not args.yes:
        parser.error("reset_database requires --yes to acknowledge the destructive operation.")

    _apply_environment_overrides(args)

    # Reconfigure the engines if an override is provided.
    if args.database_url:
        configure_database(args.database_url, allow_fallback=False)

    print("⚠️  Dropping and recreating all tables defined in the metadata…")
    reset_schema()
    print("✅ Schema recreated successfully.")

    if args.skip_seed:
        print("ℹ️  Seed phase skipped (per --skip-seed).")
        return 0

    print("🚀 Running seed pipeline (classifier, skills, badges, roadmaps)…")
    run_seed_pipeline()
    print("✅ Database seeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
