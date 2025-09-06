# Fichier: backend/app/services/rag_utils.py (VERSION CORRIGÉE)

import logging
from sqlalchemy.orm import Session
from sqlalchemy import select

# ---------------------------------
from app.core import ai_service
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
        topic_embedding = get_embedding(topic)
        
        similar_examples = db.scalars(
            select(VectorStore)
            .filter(VectorStore.source_language == language)
            .filter(VectorStore.content_type == content_type)
            .order_by(VectorStore.embedding.l2_distance(topic_embedding))
            .limit(limit)
        ).all()

        if not similar_examples:
            logger.info(f"Aucun exemple RAG trouvé pour '{topic}' avec le type '{content_type}'.")
            return ""

        context = "Voici des exemples de haute qualité pour t'inspirer. Suis leur style, leur ton et leur structure :\n\n"
        for i, ex in enumerate(similar_examples):
            context += f"--- EXEMPLE {i+1} ---\n{ex.chunk_text}\n\n"
        
        logger.info(f"{len(similar_examples)} exemples RAG trouvés pour '{topic}'.")
        return context
    except Exception as e:
        logger.error(f"Erreur lors de la recherche RAG pour '{topic}': {e}", exc_info=True)
        return ""