"""CLI helper to validate required environment variables.

Usage::

    python -m scripts.check_env

It simply imports :mod:`app.core.config` and reports any validation errors in a
readable format, exiting with status code 1 when something is missing.
"""

from __future__ import annotations

import sys

from pydantic import ValidationError

try:
    from app.core.config import settings
except ValidationError as exc:
    # ``app.core.config`` already prints a detailed error summary, so we only
    # need to set a non-zero exit code here.
    print("Environment validation failed – see details above.", file=sys.stderr)
    sys.exit(1)
else:
    print("Environment variables OK.")
    for name, value in settings.model_dump().items():
        if "key" in name.lower() or "password" in name.lower():
            print(f"- {name}: <hidden>")
        else:
            print(f"- {name}: {value}")
