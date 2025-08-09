# Fichier: backend/app/crud/course_crud.py (VERSION FINALE)
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import not_, select
from app.models import course_model, level_model, user_model, user_course_progress_model
from app.schemas import course_schema
from app.core.ai_service import generate_learning_plan, classify_course_topic
import logging

logger = logging.getLogger(__name__)

def generate_course_content_task(db: Session, course_id: int, creator_id: int):
    """
    Tâche de fond pour générer le contenu d'un cours.
    """
    logger.info(f"Début de la tâche de fond pour le cours ID: {course_id}")
    db_course = db.get(course_model.Course, course_id)
    if not db_course:
        logger.error(f"Tâche de fond annulée : cours {course_id} non trouvé.")
        return

    try:
        db_course.generation_status = "generating"
        db.commit()

        course_type = classify_course_topic(
            title=db_course.title, model_choice=db_course.model_choice
        )
        learning_plan = generate_learning_plan(
            title=db_course.title,
            course_type=course_type,
            model_choice=db_course.model_choice
        )

        db_course.description = learning_plan.get("overview", f"Un cours sur {db_course.title}")
        db_course.course_type = course_type
        db_course.learning_plan_json = learning_plan
        
        levels_data = learning_plan.get("levels", [])
        for i, level_data in enumerate(levels_data):
            db_level = level_model.Level(
                course_id=db_course.id,
                title=level_data.get("level_title", f"Niveau {i+1}"),
                level_order=i
            )
            db.add(db_level)

        creator_progress = user_course_progress_model.UserCourseProgress(
            user_id=creator_id, course_id=db_course.id, current_level_order=0
        )
        db.add(creator_progress)

        db_course.generation_status = "completed"
        db.commit()
        logger.info(f"Génération du cours ID: {course_id} terminée avec succès.")

    except Exception as e:
        logger.error(f"Erreur lors de la génération du cours ID {course_id}: {e}")
        db.rollback()
        db_course.generation_status = "failed"
        db.commit()

def create_course(db: Session, course_in: course_schema.CourseCreate, creator: user_model.User) -> course_model.Course:
    """
    Crée une entrée de cours "brouillon" et lance la génération en arrière-plan.
    """
    db_course = course_model.Course(
        title=course_in.title,
        model_choice=course_in.model_choice,
        generation_status="pending",
        course_type="unknown"
    )
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

def get_course(db: Session, course_id: int) -> course_model.Course | None:
    """Récupère un cours par son ID, en pré-chargeant les niveaux."""
    return db.query(course_model.Course).options(
        joinedload(course_model.Course.levels)
    ).filter(course_model.Course.id == course_id).first()

def get_user_courses(db: Session, user_id: int) -> list[course_model.Course]:
    """Récupère les cours auxquels un utilisateur est inscrit."""
    return db.query(course_model.Course).join(
        user_course_progress_model.UserCourseProgress
    ).filter(
        user_course_progress_model.UserCourseProgress.user_id == user_id
    ).order_by(course_model.Course.id.desc()).all()

def get_public_courses(db: Session, user_id: int) -> list[course_model.Course]:
    """Récupère les cours publics auxquels un utilisateur N'EST PAS inscrit."""
    
    enrolled_course_ids_sq = db.query(
        user_course_progress_model.UserCourseProgress.course_id
    ).filter(user_course_progress_model.UserCourseProgress.user_id == user_id).subquery()

    # --- CORRECTION DU WARNING ---
    # On enveloppe la sous-requête dans un select() pour être explicite.
    return db.query(course_model.Course).filter(
        course_model.Course.visibility == "public",
        not_(course_model.Course.id.in_(select(enrolled_course_ids_sq)))
    ).order_by(course_model.Course.id.desc()).all()


def enroll_user_in_course(db: Session, course_id: int, user_id: int):
    """Inscrit un utilisateur à un cours."""
    existing_progress = db.query(user_course_progress_model.UserCourseProgress).filter_by(
        user_id=user_id, course_id=course_id
    ).first()

    if existing_progress:
        return existing_progress

    new_progress = user_course_progress_model.UserCourseProgress(
        user_id=user_id,
        course_id=course_id,
        current_level_order=0
    )
    db.add(new_progress)
    db.commit()
    db.refresh(new_progress)
    return new_progress

def unenroll_user_from_course(db: Session, course_id: int, user_id: int):
    """Désinscrit un utilisateur d'un cours."""
    progress_to_delete = db.query(user_course_progress_model.UserCourseProgress).filter_by(
        user_id=user_id, course_id=course_id
    ).first()

    if progress_to_delete:
        db.delete(progress_to_delete)
        db.commit()
        return True
    return False