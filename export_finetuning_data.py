import sys
import json
import logging
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy import create_engine

# --- Configuration pour que le script puisse trouver les modules de l'app ---
sys.path.append(".")
from app.core.config import settings
from app.core import prompt_manager
from app.db.base_class import Base # noqa: F401 - Pour charger tous les modèles
from app.models.analytics.feedback_model import ContentFeedback, FeedbackStatus, FeedbackRating
from app.models.course.knowledge_component_model import KnowledgeComponent
from app.models.course.chapter_model import Chapter
from app.models.course.level_model import Level
from app.models.course.course_model import Course

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("FineTuningExporter")

# --- Fonctions de Reconstruction de Prompts ---

def reconstruct_exercise_prompt(component: KnowledgeComponent) -> dict:
    """
    Reconstruit la paire prompt/completion pour un exercice approuvé.
    """
    try:
        # 1. Récupérer le contexte original (la leçon ou le dialogue)
        lesson_context = component.chapter.lesson_text or ""

        # 2. Reconstruire le prompt système exact qui a été utilisé
        system_prompt = prompt_manager.get_prompt(
            "generic_content.exercises", # Utilise le même prompt que celui de la génération
            course_type=component.chapter.level.course.course_type,
            chapter_title=component.chapter.title,
            ensure_json=True
        )

        # 3. La "completion" est l'exercice lui-même, formaté comme l'IA l'a renvoyé
        completion_json = {
            "exercises": [
                {
                    "title": component.title,
                    "category": component.category,
                    "component_type": component.component_type,
                    "bloom_level": component.bloom_level,
                    "content_json": component.content_json
                }
            ]
        }
        
        # Le format final pour Llama 3.1
        # Il est souvent préférable de structurer le prompt de cette manière
        # pour que le modèle distingue bien le système, l'utilisateur et sa réponse attendue.
        prompt = (
            f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{system_prompt}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
            f"{lesson_context}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )

        return {
            "prompt": prompt,
            "completion": json.dumps(completion_json, ensure_ascii=False)
        }
    except Exception as e:
        logger.error(f"Échec de reconstruction pour le composant {component.id}: {e}")
        return None

# --- Logique Principale ---

def export_approved_feedback():
    """
    Exporte les feedbacks approuvés vers un fichier JSONL pour le fine-tuning.
    """
    logger.info("Connexion à la base de données...")
    sync_db_url = str(settings.DATABASE_URL).replace("+asyncpg", "")
    engine = create_engine(sync_db_url)
    SessionLocal = sessionmaker(bind=engine)
    
    db = SessionLocal()
    
    try:
        logger.info("Récupération des feedbacks 'likés' et 'approuvés'...")
        approved_feedback = db.query(ContentFeedback).filter(
            ContentFeedback.status == FeedbackStatus.approved,
            ContentFeedback.rating == FeedbackRating.liked
        ).all()

        if not approved_feedback:
            logger.info("Aucun nouveau feedback approuvé à exporter.")
            return

        finetuning_data = []
        logger.info(f"Traitement de {len(approved_feedback)} feedbacks...")

        for feedback in approved_feedback:
            data_pair = None
            if feedback.content_type == 'knowledge_component':
                component = db.query(KnowledgeComponent).options(
                    joinedload(KnowledgeComponent.chapter)
                    .joinedload(Chapter.level)
                    .joinedload(Level.course)
                ).filter(KnowledgeComponent.id == feedback.content_id).first()
                
                if component:
                    data_pair = reconstruct_exercise_prompt(component)
                else:
                    logger.warning(f"Composant ID {feedback.content_id} non trouvé.")
            
            # (Vous pourrez ajouter ici la logique pour d'autres types de contenu plus tard)

            if data_pair:
                finetuning_data.append(data_pair)

        output_file = "finetuning_dataset.jsonl"
        logger.info(f"Écriture de {len(finetuning_data)} paires dans le fichier '{output_file}'...")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in finetuning_data:
                # Le format JSONL est une ligne par objet JSON
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                
        logger.info(f"✅ Export terminé avec succès ! Le fichier '{output_file}' est prêt.")

    finally:
        db.close()

if __name__ == "__main__":
    export_approved_feedback()