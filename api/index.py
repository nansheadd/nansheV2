"""Entrypoint for deploying the FastAPI backend on Vercel."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the application package is importable when executed by Vercel.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.main import app as fastapi_app  # noqa: E402

# Vercel looks for a module-level ``app`` variable.
app = fastapi_app
