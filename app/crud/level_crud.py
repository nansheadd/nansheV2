# Fichier: backend/app/crud/level_crud.py (VERSION FINALE)
from sqlalchemy.orm import Session, joinedload
from app.models import level_model, chapter_model, user_course_progress_model
from app.core.ai_service import generate_chapter_plan_for_level
import logging

logger = logging.getLogger(__name__)

def get_level_with_chapters(db: Session, level_id: int, user_id: int):
    """
    Récupère un niveau, vérifie les droits d'accès, et génère le plan des chapitres
    en utilisant le modèle IA correct (stocké dans le cours parent).
    """
    # 1. Trouver le niveau et pré-charger son cours parent pour accéder au model_choice
    level = db.query(level_model.Level).options(
        joinedload(level_model.Level.chapters),
        joinedload(level_model.Level.course) 
    ).filter_by(id=level_id).first()

    if not level:
        return None

    # 2. Vérifier les droits d'accès
    progress = db.query(user_course_progress_model.UserCourseProgress).filter_by(
        user_id=user_id, course_id=level.course_id
    ).first()
    
    if not progress or level.level_order > progress.current_level_order:
        return None

    # 3. Générer le plan des chapitres si nécessaire
    if not level.are_chapters_generated:
        logger.info(f"Plan de chapitres non trouvé pour '{level.title}'. Génération IA avec le modèle '{level.course.model_choice}'...")
        
        # On passe le model_choice du cours parent à la fonction de l'IA
        chapter_titles = generate_chapter_plan_for_level(
            level_title=level.title,
            model_choice=level.course.model_choice 
        )
        
        for i, title in enumerate(chapter_titles):
            chapter = chapter_model.Chapter(level_id=level.id, title=title, chapter_order=i)
            db.add(chapter)
        
        level.are_chapters_generated = True
        db.add(level)
        db.commit()
        db.refresh(level)
        logger.info(f"Génération du plan de chapitres terminée pour '{level.title}'.")
    
    return level