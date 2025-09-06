# Fichier: backend/app/crud/level_crud.py (FINAL COMPLET)
import logging
from app.models.course import chapter_model
from app.models.course import level_model
from sqlalchemy.orm import Session, joinedload
from app.models.progress import user_course_progress_model
from app.core.ai_service import generate_chapter_plan_for_level

logger = logging.getLogger(__name__)

def get_level_with_chapters(db: Session, level_id: int, user_id: int):
    """
    Récupère un niveau avec ses chapitres et définit l'accès pour l'utilisateur.
    La génération est maintenant gérée ailleurs.
    """
    level = db.query(level_model.Level).options(
        joinedload(level_model.Level.chapters),
        joinedload(level_model.Level.course)
    ).filter_by(id=level_id).first()

    if not level:
        return None

    progress = db.query(user_course_progress_model.UserCourseProgress).filter_by(
        user_id=user_id, course_id=level.course_id
    ).first()

    if not progress:
        for chapter in level.chapters:
            chapter.is_accessible = False
        return level

    user_chapter_progress_index = -1
    if progress.current_level_order > level.level_order:
        user_chapter_progress_index = float('inf')
    elif progress.current_level_order == level.level_order:
        user_chapter_progress_index = progress.current_chapter_order
    
    for chapter in level.chapters:
        chapter.is_accessible = chapter.chapter_order <= user_chapter_progress_index
    
    return level