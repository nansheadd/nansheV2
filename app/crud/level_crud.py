# Fichier: backend/app/crud/level_crud.py (FINAL COMPLET)
import logging
from sqlalchemy.orm import Session, joinedload
from app.models import level_model, chapter_model, user_course_progress_model
from app.core.ai_service import generate_chapter_plan_for_level

logger = logging.getLogger(__name__)

def get_level_with_chapters(db: Session, level_id: int, user_id: int):
    """
    Récupère un niveau, vérifie et définit l'accès pour chaque chapitre,
    et génère le plan des chapitres "Juste-à-Temps" si cela n'a pas encore été fait.
    """
    # 1. Récupérer le niveau et les relations nécessaires (cours et chapitres)
    level = db.query(level_model.Level).options(
        joinedload(level_model.Level.chapters),
        joinedload(level_model.Level.course)
    ).filter_by(id=level_id).first()

    if not level:
        return None

    # 2. Récupérer la progression de l'utilisateur pour ce cours spécifique
    progress = db.query(user_course_progress_model.UserCourseProgress).filter_by(
        user_id=user_id, course_id=level.course_id
    ).first()

    # Si l'utilisateur n'est pas inscrit, aucun chapitre n'est accessible
    if not progress:
        for chapter in level.chapters:
            chapter.is_accessible = False
        return level

    # 3. Générer les chapitres à la volée si ce n'est pas déjà fait
    if not level.are_chapters_generated:
        logger.info(f"Génération JIT des chapitres pour '{level.title}'...")
        chapter_titles = generate_chapter_plan_for_level(
            level_title=level.title,
            model_choice=level.course.model_choice
        )
        if chapter_titles:
            for i, title in enumerate(chapter_titles):
                db.add(chapter_model.Chapter(level_id=level.id, title=title, chapter_order=i))
            level.are_chapters_generated = True
            db.commit()
            db.refresh(level)
        else:
            logger.error(f"Échec de la génération JIT des chapitres pour le niveau {level.id}")

    # 4. Déterminer le niveau de progression de l'utilisateur dans ce niveau
    user_chapter_progress_index = -1
    if progress.current_level_order > level.level_order:
        # Si l'utilisateur a déjà terminé ce niveau, tous les chapitres sont accessibles.
        user_chapter_progress_index = float('inf')
    elif progress.current_level_order == level.level_order:
        # Si l'utilisateur est sur ce niveau, on regarde sa progression dans les chapitres.
        user_chapter_progress_index = progress.current_chapter_order
    
    # 5. Appliquer la logique d'accessibilité à chaque chapitre
    for chapter in level.chapters:
        chapter.is_accessible = chapter.chapter_order <= user_chapter_progress_index
    
    return level