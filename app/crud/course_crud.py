# Fichier: backend/app/crud/course_crud.py (REFONTE)
from sqlalchemy.orm import Session
from typing import List
from app.models import course_model, level_model, user_model, user_course_progress_model
from app.schemas import course_schema
from app.core.ai_service import generate_learning_plan

def create_course(db: Session, course_in: course_schema.CourseCreate, creator: user_model.User) -> course_model.Course:
    """
    Crée un nouveau cours, son plan de niveaux, et inscrit automatiquement le créateur.
    """
    # Étape 1 : Générer le plan de cours (liste des niveaux)
    learning_plan = generate_learning_plan(course_in.title, "default") # course_type est moins crucial maintenant

    # Étape 2 : Créer l'objet Course principal
    db_course = course_model.Course(
        title=course_in.title,
        description=learning_plan.get("overview", f"Un cours sur {course_in.title}"),
        course_type=learning_plan.get("course_type", "general"), # L'IA peut suggérer un type
        learning_plan_json=learning_plan,
        # creator_id=creator.id # On pourrait ajouter cette relation
    )
    db.add(db_course)
    db.flush()  # Pour obtenir l'ID du cours avant le commit

    # Étape 3 : Créer les "coquilles" de niveaux vides
    levels_data = learning_plan.get("levels", [])
    for i, level_data in enumerate(levels_data):
        db_level = level_model.Level(
            course_id=db_course.id,
            title=level_data.get("level_title", f"Niveau {i+1}"),
            level_order=i
        )
        db.add(db_level)
        
    # Étape 4 : Inscrire le créateur au cours
    creator_progress = user_course_progress_model.UserCourseProgress(
        user_id=creator.id,
        course_id=db_course.id,
        current_level_order=0 # Il commence au niveau 0
    )
    db.add(creator_progress)
    
    db.commit()
    db.refresh(db_course)
    return db_course

def get_course(db: Session, course_id: int) -> course_model.Course | None:
    """Récupère un cours par son ID."""
    return db.get(course_model.Course, course_id)

def get_courses(db: Session) -> List[course_model.Course]:
    """Récupère tous les cours de la base de données."""
    return db.query(course_model.Course).order_by(course_model.Course.id.desc()).all()