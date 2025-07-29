# Fichier: backend/app/crud/level_crud.py (REFONTE)
from sqlalchemy.orm import Session, joinedload
from app.models import level_model, chapter_model, user_course_progress_model
from app.core.ai_service import generate_chapter_plan_for_level
import logging

logger = logging.getLogger(__name__)

def get_level_with_chapters(db: Session, course_id: int, level_order: int, user_id: int):
    """
    Récupère un niveau et son plan de chapitres.
    Si le plan n'existe pas, il est généré par l'IA.
    Vérifie les droits d'accès de l'utilisateur.
    """
    # 1. Vérifier les droits d'accès
    progress = db.query(user_course_progress_model.UserCourseProgress).filter_by(
        user_id=user_id, course_id=course_id
    ).first()
    
    if not progress or level_order > progress.current_level_order:
        logger.warning(f"Accès refusé pour l'utilisateur {user_id} au niveau {level_order}.")
        return None

    # 2. Trouver le niveau
    level = db.query(level_model.Level).options(
        joinedload(level_model.Level.chapters) # Pré-charge les chapitres
    ).filter_by(course_id=course_id, level_order=level_order).first()

    if not level: return None

    # 3. Générer le plan des chapitres si c'est la première fois
    if not level.are_chapters_generated:
        logger.info(f"Plan de chapitres non trouvé pour '{level.title}'. Génération IA...")
        
        chapter_titles = generate_chapter_plan_for_level(level.title)
        
        for i, title in enumerate(chapter_titles):
            chapter = chapter_model.Chapter(
                level_id=level.id,
                title=title,
                chapter_order=i
            )
            db.add(chapter)
        
        level.are_chapters_generated = True
        db.add(level)
        db.commit()
        db.refresh(level)
        logger.info(f"Génération du plan de chapitres terminée pour '{level.title}'.")
    
    return level