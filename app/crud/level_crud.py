# Fichier: backend/app/crud/level_crud.py (VERSION CORRIGÉE pour le JIT)
import logging
from sqlalchemy.orm import Session, joinedload
from app.models import level_model, chapter_model, user_course_progress_model
from app.core.ai_service import generate_chapter_plan_for_level

logger = logging.getLogger(__name__)

def get_level_with_chapters(db: Session, level_id: int, user_id: int):
    """
    Récupère un niveau, vérifie les droits d'accès, et génère le plan des chapitres
    "Juste-à-Temps" si cela n'a pas encore été fait.
    """
    # 1. Trouver le niveau et charger le cours parent pour le CONTEXTE
    level = db.query(level_model.Level).options(
        joinedload(level_model.Level.chapters),
        joinedload(level_model.Level.course) # Important pour le contexte !
    ).filter_by(id=level_id).first()

    if not level: return None

    # 2. Vérifier les droits d'accès (logique existante, parfaite)
    progress = db.query(user_course_progress_model.UserCourseProgress).filter_by(
        user_id=user_id, course_id=level.course_id
    ).first()
    if not progress or level.level_order > progress.current_level_order:
        return None # Accès refusé

    # 3. DÉCLENCHEUR DE GÉNÉRATION JIT
    if not level.are_chapters_generated:
        logger.info(f"Génération JIT des chapitres pour '{level.title}'...")
        
        # On passe le contexte global (titre du cours) à la fonction de l'IA
        # (Nécessite une petite modification du prompt dans ai_service)
        chapter_titles = generate_chapter_plan_for_level(
            level_title=level.title,
            model_choice=level.course.model_choice,
            # Idéalement, on ajouterait un argument "course_context" ici
        )
        
        if chapter_titles:
            for i, title in enumerate(chapter_titles):
                chapter = chapter_model.Chapter(level_id=level.id, title=title, chapter_order=i)
                db.add(chapter)
            
            level.are_chapters_generated = True
            db.add(level)
            db.commit()
            db.refresh(level)
            logger.info(f"Génération JIT des chapitres terminée pour '{level.title}'.")
        else:
            logger.error(f"Échec de la génération JIT des chapitres pour le niveau {level.id}")

    return level