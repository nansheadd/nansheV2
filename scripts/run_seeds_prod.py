"""Utility script to seed the production database with explicit credentials.

Edit the :data:`ENVIRONMENT_OVERRIDES` dictionary and replace every
``"XXX"`` placeholder with your real secrets before executing the script::

    python -m scripts.run_seeds_prod

The script injects the provided values into ``os.environ`` before importing the
regular ``run_seeds`` helpers. Doing so ensures the Pydantic configuration model
reads the production credentials even when you launch the command from your
local terminal.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict

# ---------------------------------------------------------------------------
# IMPORTANT: replace all placeholder values before running the script.
# ---------------------------------------------------------------------------
ENVIRONMENT_OVERRIDES: Dict[str, str] = {
    # Core application settings ------------------------------------------------
    "DATABASE_URL": "postgresql+asyncpg://user:password@host:5432/database",  # <-- replace
    "SECRET_KEY": "XXX",
    "ENVIRONMENT": "production",
    "FRONTEND_BASE_URL": "https://nanshe-v2.vercel.app",
    "BACKEND_BASE_URL": "https://nanshe-v2.vercel.app",

    # Email / transactional messaging -----------------------------------------
    "RESEND_API_KEY": "XXX",
    "EMAIL_FROM": "hello@nanshe.ai",
    "MAIL_PROVIDER": "resend",  # keep "resend" unless you switch providers
    "RESEND_WEBHOOK_SECRET": "XXX",

    # AI providers -------------------------------------------------------------
    "OPENAI_API_KEY": "XXX",
    "GOOGLE_API_KEY": "XXX",
    "REPLICATE_API_TOKEN": "XXX",
    "USE_REMOTE_EMBEDDINGS": "true",  # set to "false" to fallback to local hashing

    # Payments -----------------------------------------------------------------
    "STRIPE_SECRET_KEY": "XXX",
    "STRIPE_PUBLISHABLE_KEY": "XXX",
    "STRIPE_PREMIUM_PRICE_ID": "XXX",
    "STRIPE_WEBHOOK_SECRET": "XXX",

    # Vector store -------------------------------------------------------------
    "SUPABASE_URL": "https://your-supabase-project.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "XXX",
}


def _apply_environment_overrides() -> None:
    """Populate ``os.environ`` with the configured overrides.

    A defensive check ensures no placeholder values remain in the dictionary so
    we avoid accidentally seeding with invalid credentials.
    """

    placeholders = {"XXX", "https://your-supabase-project.supabase.co"}
    missing = [
        name
        for name, value in ENVIRONMENT_OVERRIDES.items()
        if not value or value.strip() in placeholders
    ]

    if missing:
        formatted = ", ".join(missing)
        raise RuntimeError(
            "Replace the placeholder values in ENVIRONMENT_OVERRIDES before running"
            f" the seeding script. Missing: {formatted}"
        )

    for name, value in ENVIRONMENT_OVERRIDES.items():
        os.environ[name] = value


# Apply overrides **before** importing modules that rely on app settings.
_apply_environment_overrides()

# Ensure the project root is on ``sys.path`` so our relative imports work when
# the script is executed via ``python -m`` from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from sqlalchemy import text  # noqa: E402  (import after sys.path manipulation)

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, sync_engine  # noqa: E402
from scripts import run_seeds  # noqa: E402


def main() -> None:
    """Run the canonical seeding pipeline against the production database."""

    session = SessionLocal()
    try:
        with sync_engine.connect() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=sync_engine)

        system_user = run_seeds.get_or_create_default_user(session)
        run_seeds.seed_classifier_examples(session)
        run_seeds.seed_skills(session)
        run_seeds.seed_badges(session)
        run_seeds.seed_language_roadmaps(session, system_user)
    finally:
        session.close()


if __name__ == "__main__":
    main()
