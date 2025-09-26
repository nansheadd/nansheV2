"""Utilities for classifying user input against the vector store."""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.models.analytics.vector_store_model import VectorStore
from app.services.rag_utils import get_embedding
from app.core.embeddings import cosine_similarity, ensure_dimension, normalize_vector

logger = logging.getLogger(__name__)


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

        input_embedding = normalize_vector(get_embedding(text))
        if not input_embedding or not any(abs(v) > 0 for v in input_embedding):
            logger.warning("--- [DB_CLASSIFIER] Embedding vide pour le texte fourni.")
            return []

        stored_vectors = db.query(VectorStore).all()
        if not stored_vectors:
            logger.warning("--- [DB_CLASSIFIER] La base vectorielle est vide.")
            return []

        enriched: list[tuple[VectorStore, float]] = []
        for vector_row in stored_vectors:
            try:
                raw_embedding = list(vector_row.embedding)
            except TypeError:
                raw_embedding = []

            if not raw_embedding:
                continue

            aligned = ensure_dimension(raw_embedding, len(input_embedding))
            aligned = normalize_vector(aligned)
            score = cosine_similarity(input_embedding, aligned)
            enriched.append((vector_row, score))

        if not enriched:
            logger.warning("--- [DB_CLASSIFIER] Aucun embedding valide trouvé dans la base.")
            return []

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


db_classifier = DBClassifier()
