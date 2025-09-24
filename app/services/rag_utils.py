# Fichier: backend/app/services/rag_utils.py (VERSION CORRIGÉE)

import logging
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.core import ai_service
from app.core.embeddings import (
    cosine_similarity,
    ensure_dimension,
    normalize_vector,
)
from app.models.analytics.vector_store_model import VectorStore

logger = logging.getLogger(__name__)


def get_embedding(text: str):
    """
    Wrapper pour obtenir l'embedding d'un texte via le ai_service.
    """
    return ai_service.get_text_embedding(text)
# -------------------------


def _find_similar_examples(db: Session, topic: str, language: str, content_type: str, limit: int = 3) -> str:
    """
    Cherche des exemples similaires dans la base vectorielle et les formate pour un prompt.
    """
    try:
        # Utilise maintenant la fonction get_embedding locale pour la cohérence
        topic_embedding = normalize_vector(get_embedding(topic))
        if not any(topic_embedding):
            logger.info("Embedding vide pour le sujet '%s', aucun contexte RAG retourné.", topic)
            return ""

        candidates: List[VectorStore] = (
            db.query(VectorStore)
            .filter(VectorStore.source_language == language)
            .filter(VectorStore.content_type == content_type)
            .all()
        )

        scored: List[Tuple[VectorStore, float]] = []
        for entry in candidates:
            raw_embedding = entry.embedding or []
            if not raw_embedding:
                continue

            aligned = normalize_vector(ensure_dimension(raw_embedding, len(topic_embedding)))
            similarity = cosine_similarity(topic_embedding, aligned)
            if similarity <= 0:
                continue
            scored.append((entry, similarity))

        if not scored:
            logger.info(
                "Aucun exemple RAG trouvé pour '%s' avec le type '%s'.",
                topic,
                content_type,
            )
            return ""

        top_matches = [entry for entry, _ in sorted(scored, key=lambda item: item[1], reverse=True)[:limit]]

        context = "Voici des exemples de haute qualité pour t'inspirer. Suis leur style, leur ton et leur structure :\n\n"
        for i, ex in enumerate(top_matches):
            context += f"--- EXEMPLE {i+1} ---\n{ex.chunk_text}\n\n"

        logger.info("%s exemples RAG trouvés pour '%s'.", len(top_matches), topic)
        return context
    except Exception as e:
        logger.error(f"Erreur lors de la recherche RAG pour '{topic}': {e}", exc_info=True)
        return ""