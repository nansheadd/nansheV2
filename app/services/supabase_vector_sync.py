"""Utility helpers to synchronise JSONL training data with Supabase vectors.

This module is executed during the FastAPI startup sequence.  It loads a
JSONL dataset, generates embeddings for each entry and upserts the records into
the configured Supabase table that uses the ``vector`` extension.  The module
is intentionally resilient so that missing environment variables or network
failures do not crash the application startup but instead emit actionable
logs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Sequence

import requests

from app.core.config import settings
from app.core.embeddings import EMBEDDING_DIMENSION, get_text_embedding


logger = logging.getLogger(__name__)


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from *path* line by line.

    Invalid lines are skipped with a warning instead of raising an exception so
    a single malformed example does not break the ingestion.
    """

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                text = raw_line.strip()
                if not text:
                    continue

                try:
                    yield json.loads(text)
                except json.JSONDecodeError as exc:  # pragma: no cover - log only
                    logger.warning(
                        "JSONL line %s ignored (%s): %s",
                        line_number,
                        exc.msg,
                        text[:120],
                    )
    except FileNotFoundError:
        logger.error("Fichier JSONL introuvable: %s", path)
    except OSError as exc:
        logger.error("Impossible de lire le fichier JSONL '%s': %s", path, exc)


def _batched(iterable: Iterable[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []

    if batch:
        yield batch


def _build_payload(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform raw JSONL rows into Supabase payload dictionaries."""

    payload: list[dict[str, Any]] = []

    for record in records:
        text = (record.get("text") or record.get("chunk_text") or "").strip()
        if not text:
            logger.debug("Entrée ignorée (texte manquant): %s", record)
            continue

        embedding = get_text_embedding(text)
        if len(embedding) != EMBEDDING_DIMENSION:
            logger.warning(
                "Dimension d'embedding inattendue pour '%s' (attendu=%s, obtenu=%s)",
                text[:80],
                EMBEDDING_DIMENSION,
                len(embedding),
            )
            continue

        metadata: Dict[str, Any] = {
            key: value
            for key, value in record.items()
            if key not in {"text", "chunk_text", "domain", "area", "skill", "main_skill"}
        }

        payload.append(
            {
                "chunk_text": text,
                "embedding": embedding,
                "domain": record.get("domain"),
                "area": record.get("area"),
                "skill": record.get("skill") or record.get("main_skill"),
                "metadata_": metadata or None,
            }
        )

    return payload


def _supabase_headers(schema: str | None) -> dict[str, str] | None:
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not key:
        return None

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    profile = (schema or "public").strip()
    if profile and profile != "public":
        headers["Content-Profile"] = profile
        headers["Accept-Profile"] = profile

    return headers


def _supabase_table_url() -> tuple[str, str] | tuple[None, None]:
    base_url = settings.SUPABASE_URL
    if not base_url:
        return None, None

    table = settings.SUPABASE_VECTOR_TABLE.strip()
    schema = settings.SUPABASE_VECTOR_SCHEMA.strip()
    if not table:
        logger.error("Nom de table Supabase invalide.")
        return None, None

    normalized = str(base_url).rstrip("/")
    return f"{normalized}/rest/v1/{table}", schema


def seed_supabase_vector_store() -> None:
    """Load embeddings from the JSONL source file and upsert them to Supabase."""

    url, schema = _supabase_table_url()
    headers = _supabase_headers(schema)
    if headers is None:
        logger.info("Clé de service Supabase manquante : synchronisation vectorielle ignorée.")
        return

    if url is None:
        logger.info("URL Supabase invalide : synchronisation vectorielle ignorée.")
        return

    source_path = Path(settings.SUPABASE_VECTOR_SOURCE_FILE)
    if not source_path.is_file():
        logger.warning("Fichier de données vectorielles introuvable : %s", source_path)
        return

    logger.info("Synchronisation Supabase Vector depuis %s", source_path)

    params = {}
    conflict_column = settings.SUPABASE_VECTOR_ON_CONFLICT.strip()
    if conflict_column:
        params["on_conflict"] = conflict_column

    batch_size = max(1, int(settings.SUPABASE_VECTOR_BATCH_SIZE or 1))

    for batch in _batched(_iter_jsonl(source_path), batch_size):
        payload = _build_payload(batch)
        if not payload:
            continue

        try:
            response = requests.post(url, json=payload, headers=headers, params=params, timeout=30)
        except requests.RequestException as exc:  # pragma: no cover - network errors
            logger.error("Erreur de connexion à Supabase: %s", exc)
            return

        if response.status_code >= 400:
            logger.error(
                "Échec de l'upsert Supabase (%s): %s",
                response.status_code,
                response.text,
            )
            return

    logger.info("Synchronisation Supabase Vector terminée.")


async def ensure_supabase_vector_sync() -> None:
    """Trigger the Supabase vector seeding asynchronously during startup."""

    if not settings.SUPABASE_VECTOR_SYNC_ON_STARTUP:
        logger.info("Synchronisation Supabase désactivée par configuration.")
        return

    # ``requests`` is blocking, run the seeding in a worker thread to avoid
    # blocking the FastAPI event loop on startup.
    try:
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, seed_supabase_vector_store)
    except RuntimeError:
        # Pas de boucle d'événement (context synchrone), exécute directement.
        seed_supabase_vector_store()
