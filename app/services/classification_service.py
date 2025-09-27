"""Utilities for classifying user input against the vector store."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from collections.abc import Iterable
from typing import List, Sequence

from sqlalchemy.orm import Session

from app.models.analytics.vector_store_model import VectorStore
from app.services.rag_utils import get_embedding
from app.core.embeddings import cosine_similarity, ensure_dimension, normalize_vector

logger = logging.getLogger(__name__)


def _to_float_list(value: object) -> list[float]:
    """Best-effort conversion of pgvector/array values to a Python list."""

    if value is None:
        return []

    if isinstance(value, list):
        return [float(v) for v in value]

    if isinstance(value, tuple):
        return [float(v) for v in value]

    if isinstance(value, Iterable):  # covers pgvector.Vector which is iterable
        try:
            return [float(v) for v in value]
        except Exception:  # pragma: no cover - extremely defensive
            pass

    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return [float(v) for v in tolist()]
        except Exception:  # pragma: no cover - defensive
            return []

    return []


class DBClassifier:
    """Simple cosine-similarity classifier backed by the VectorStore table."""

    def __init__(self, default_threshold: float | None = None) -> None:
        from app.core.config import settings

        if default_threshold is None:
            default_threshold = settings.DB_CLASSIFIER_DEFAULT_THRESHOLD

        try:
            self._default_threshold = float(default_threshold)
        except (TypeError, ValueError):  # pragma: no cover - defensive branch
            self._default_threshold = 0.0

        if self._default_threshold < 0:
            self._default_threshold = 0.0

    @property
    def default_threshold(self) -> float:
        return self._default_threshold

    def classify(
        self,
        text: str,
        db: Session,
        top_k: int = 1,
        threshold: float | None = None,
    ) -> List[dict]:
        logger.info("--- [DB_CLASSIFIER] Recherche des '%s' correspondances pour '%s'", top_k, text)

        if threshold is None:
            threshold = self._default_threshold

        if not text or not text.strip():
            logger.warning("--- [DB_CLASSIFIER] Texte d'entrée vide.")
            return []

        stored_vectors = db.query(VectorStore).all()
        if not stored_vectors:
            logger.warning("--- [DB_CLASSIFIER] La base vectorielle est vide.")
            return []

        if not self._has_embeddings(stored_vectors):
            logger.info("--- [DB_CLASSIFIER] Aucun embedding détecté, fallback textuel activé.")
            return self._classify_without_embeddings(text, stored_vectors, top_k, threshold)

        input_embedding = normalize_vector(get_embedding(text))
        if not input_embedding or not any(abs(v) > 0 for v in input_embedding):
            logger.warning("--- [DB_CLASSIFIER] Embedding vide pour le texte fourni. Fallback textuel utilisé.")
            return self._classify_without_embeddings(text, stored_vectors, top_k, threshold)

        enriched: list[tuple[VectorStore, float]] = []
        for vector_row in stored_vectors:
            raw_embedding = _to_float_list(getattr(vector_row, "embedding", None))

            if not raw_embedding:
                continue

            aligned = ensure_dimension(raw_embedding, len(input_embedding))
            aligned = normalize_vector(aligned)
            score = cosine_similarity(input_embedding, aligned)
            enriched.append((vector_row, score))

        if not enriched:
            logger.warning("--- [DB_CLASSIFIER] Aucun embedding valide trouvé dans la base. Fallback textuel utilisé.")
            return self._classify_without_embeddings(text, stored_vectors, top_k, threshold)

        results_with_scores = sorted(enriched, key=lambda item: item[1], reverse=True)

        final_results: List[dict] = []
        for vector, score in results_with_scores[: top_k or 1]:
            if score < threshold:
                logger.warning(
                    "    -> Match ignoré: '%s' (score %.4f < %.2f)",
                    vector.chunk_text,
                    score,
                    threshold,
                )
                continue

            logger.info(
                "    -> Match trouvé: '%s' (Skill: %s) score=%.4f",
                vector.chunk_text,
                vector.skill,
                score,
            )
            final_results.append(
                {
                    "category": {
                        "name": vector.skill,
                        "domain": vector.domain,
                        "area": vector.area,
                    },
                    "confidence": float(score),
                    "source_text": vector.chunk_text,
                }
            )

        if not final_results:
            logger.error("--- [DB_CLASSIFIER] Aucun match au-dessus du seuil.")

        return final_results

    def _has_embeddings(self, entries: Sequence[VectorStore]) -> bool:
        """Return True if at least one entry contains a non-empty embedding."""

        for entry in entries:
            values = _to_float_list(getattr(entry, "embedding", None))
            if any(abs(v) > 0 for v in values):
                return True
        return False

    def _classify_without_embeddings(
        self,
        text: str,
        stored_vectors: Sequence[VectorStore],
        top_k: int,
        threshold: float,
    ) -> List[dict]:
        """Fallback classifier using plain-text similarity when embeddings are missing."""

        normalized_input = text.strip().lower()
        scored: list[tuple[VectorStore, float]] = []

        for vector in stored_vectors:
            candidate = (vector.chunk_text or "").strip()
            if not candidate:
                continue

            candidate_norm = candidate.lower()
            if not candidate_norm:
                continue

            if normalized_input == candidate_norm:
                score = 1.0
            elif normalized_input in candidate_norm or candidate_norm in normalized_input:
                score = 0.95
            else:
                score = SequenceMatcher(None, normalized_input, candidate_norm).ratio()

            scored.append((vector, score))

        if not scored:
            logger.warning("--- [DB_CLASSIFIER] Aucun texte valide disponible pour le fallback.")
            return []

        results_with_scores = sorted(scored, key=lambda item: item[1], reverse=True)

        final_results: List[dict] = []
        for vector, score in results_with_scores[: top_k or 1]:
            if score < threshold:
                logger.warning(
                    "    -> Match ignoré: '%s' (score %.4f < %.2f)",
                    vector.chunk_text,
                    score,
                    threshold,
                )
                continue

            logger.info(
                "    -> Match (fallback) trouvé: '%s' (Skill: %s) score=%.4f",
                vector.chunk_text,
                vector.skill,
                score,
            )
            final_results.append(
                {
                    "category": {
                        "name": vector.skill,
                        "domain": vector.domain,
                        "area": vector.area,
                    },
                    "confidence": float(score),
                    "source_text": vector.chunk_text,
                }
            )

        if not final_results:
            logger.error("--- [DB_CLASSIFIER] Aucun match texte au-dessus du seuil.")

        return final_results


db_classifier = DBClassifier()
