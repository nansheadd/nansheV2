"""Utility helpers for generating and comparing text embeddings.

This module replaces the previous dependency on heavy machine learning
libraries with a lightweight hashing-based embedding strategy. When the
OPENAI_API_KEY is configured and ``USE_REMOTE_EMBEDDINGS`` is enabled, the
functions can transparently delegate to OpenAI's embedding API and then
project the result down to the dimensionality expected by the application.
Otherwise, a deterministic bag-of-words hashing scheme is used. The fallback
keeps the API responsive in serverless environments such as Vercel without
requiring gigabytes of dependencies during the build step.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache
from typing import Iterable, Sequence

from app.core.config import settings

try:  # pragma: no cover - imported lazily when available
    from openai import OpenAI
except Exception:  # pragma: no cover - keep import optional
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION: int = settings.EMBEDDING_DIMENSION
_DEFAULT_ZERO_VECTOR: tuple[float, ...] = tuple(0.0 for _ in range(EMBEDDING_DIMENSION))

_TOKEN_PATTERN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+", re.UNICODE)

_openai_client: OpenAI | None = None
if settings.OPENAI_API_KEY and settings.USE_REMOTE_EMBEDDINGS and OpenAI is not None:
    try:  # pragma: no cover - depends on environment
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("✅ Client OpenAI pour les embeddings configuré.")
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("Impossible d'initialiser OpenAI pour les embeddings : %s", exc)
        _openai_client = None


def _tokenize(text: str) -> list[str]:
    """Return a list of lowercase tokens extracted from *text*."""
    if not text:
        return []
    return _TOKEN_PATTERN.findall(text.lower())


def _character_ngrams(token: str, min_n: int = 3, max_n: int = 5) -> Iterable[str]:
    token = f"^{token}$"
    length = len(token)
    upper = min(max_n, length)
    for n in range(min_n, upper + 1):
        for i in range(length - n + 1):
            yield token[i : i + n]


def _extract_features(text: str) -> list[str]:
    tokens = _tokenize(text)
    if not tokens:
        return []

    features: list[str] = tokens.copy()

    # Ajouter des bigrammes de mots pour capturer un peu de contexte.
    for i in range(len(tokens) - 1):
        features.append(f"{tokens[i]}_{tokens[i + 1]}")

    # Ajouter des n-grammes de caractères pour davantage de robustesse.
    for token in tokens:
        features.extend(_character_ngrams(token))

    return features


def _normalize(values: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(v) * float(v) for v in values))
    if not norm:
        return [float(v) for v in values]
    return [float(v) / norm for v in values]


def _project_dimension(values: Sequence[float], dimension: int) -> list[float]:
    if dimension <= 0:
        raise ValueError("dimension must be greater than zero")
    if len(values) == dimension:
        return [float(v) for v in values]
    projected = [0.0] * dimension
    for idx, value in enumerate(values):
        projected[idx % dimension] += float(value)
    return projected


def _hashed_embedding(text: str) -> list[float]:
    features = _extract_features(text)
    if not features:
        return [0.0] * EMBEDDING_DIMENSION

    vector = [0.0] * EMBEDDING_DIMENSION
    for position, feature in enumerate(features):
        digest = hashlib.sha256(f"{position}:{feature}".encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign

    return _normalize(vector)


def _call_openai_embedding(text: str) -> list[float]:
    if not _openai_client:
        return []
    try:  # pragma: no cover - réseau externe
        response = _openai_client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=text,
        )
        data = response.data[0].embedding
        if not data:
            return []
        projected = _project_dimension(data, EMBEDDING_DIMENSION)
        return _normalize(projected)
    except Exception as exc:  # pragma: no cover - dépend de l'API
        logger.warning("Fallback hashing embedding (OpenAI error: %s)", exc)
        return []


@lru_cache(maxsize=4096)
def _cached_embedding(text: str, allow_remote: bool) -> tuple[float, ...]:
    clean_text = (text or "").strip()
    if not clean_text:
        return _DEFAULT_ZERO_VECTOR

    if allow_remote:
        remote_embedding = _call_openai_embedding(clean_text)
        if remote_embedding:
            return tuple(remote_embedding)

    hashed = _hashed_embedding(clean_text)
    return tuple(hashed)


def get_text_embedding(text: str, *, allow_remote: bool | None = None) -> list[float]:
    """Return an embedding for *text*.

    ``allow_remote`` forces or forbids the usage of the remote embedding API.
    When ``None`` the global ``USE_REMOTE_EMBEDDINGS`` configuration is used.
    """

    use_remote = settings.USE_REMOTE_EMBEDDINGS if allow_remote is None else allow_remote
    return list(_cached_embedding(text, bool(use_remote)))


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for a, b in zip(vec_a, vec_b):
        af = float(a)
        bf = float(b)
        dot += af * bf
        norm_a += af * af
        norm_b += bf * bf

    if not norm_a or not norm_b:
        return 0.0

    return dot / math.sqrt(norm_a * norm_b)


def normalize_vector(values: Sequence[float]) -> list[float]:
    if not values:
        return [0.0] * EMBEDDING_DIMENSION
    return _normalize(values)


def ensure_dimension(values: Sequence[float], dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Ensure *values* matches the target dimensionality."""
    return _project_dimension(values, dimension)


__all__ = [
    "EMBEDDING_DIMENSION",
    "cosine_similarity",
    "ensure_dimension",
    "get_text_embedding",
    "normalize_vector",
]
