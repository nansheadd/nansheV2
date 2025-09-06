import torch
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text, literal_column # 👈 AJOUTER 'literal_column'
from app.db.session import SessionLocal
from app.models.analytics.vector_store_model import VectorStore
from sentence_transformers import SentenceTransformer
from app.services.rag_utils import get_embedding
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DBClassifier:
    def classify(self, text: str, db: Session, top_k: int = 1, threshold: float = 0.5):
        logger.info(f"--- [DB_CLASSIFIER] Recherche des '{top_k}' correspondances les plus proches pour: '{text}'")
        
        # 1. Obtenir l'embedding du texte d'entrée
        input_embedding = get_embedding(text)
        
        # 2. Récupérer tous les vecteurs de la base de données
        all_vectors = db.query(VectorStore).all()
        if not all_vectors:
            logger.warning("--- [DB_CLASSIFIER] La base de données vectorielle est vide. Aucun entraînement trouvé.")
            return []

        # 3. Extraire les embeddings et les métadonnées
        db_embeddings = np.array([v.embedding for v in all_vectors])
        
        # 4. Calculer la similarité cosinus
        similarities = cosine_similarity([input_embedding], db_embeddings)[0]
        
        # 5. Trouver les meilleurs scores
        # On associe chaque similarité à son vecteur correspondant
        results_with_scores = sorted(zip(all_vectors, similarities), key=lambda item: item[1], reverse=True)

        # 6. Filtrer les résultats par seuil de confiance et formater la sortie
        final_results = []
        for vector, score in results_with_scores[:top_k]:
            if score >= threshold:
                logger.info(f"    -> Match trouvé: '{vector.chunk_text}' (Skill: {vector.skill}) avec un score de {score:.4f}")
                final_results.append({
                    "category": {
                        # --- LA CORRECTION EST ICI ---
                        # On s'assure de retourner le 'skill' qui est la VRAIE cible,
                        # pas le 'chunk_text' qui est juste l'exemple d'entraînement.
                        "name": vector.skill, 
                        "domain": vector.domain,
                        "area": vector.area
                    },
                    "confidence": float(score),
                    "source_text": vector.chunk_text # On garde le texte source pour le débogage
                })
            else:
                logger.warning(f"    -> Match ignoré (score trop bas): '{vector.chunk_text}' (Score: {score:.4f} < {threshold})")

        if not final_results:
            logger.error("--- [DB_CLASSIFIER] Aucun match trouvé au-dessus du seuil de confiance.")

        return final_results

db_classifier = DBClassifier()