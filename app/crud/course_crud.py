# Fichier: nanshe/backend/app/crud/course_crud.py (MIS À JOUR)
from sqlalchemy.orm import Session
from app.models.course_model import Course
from app.schemas.course_schema import CourseCreate
from app.core.ai_service import classify_course_topic, generate_learning_plan # <--- NOUVEL IMPORT

def create_course(db: Session, course_in: CourseCreate) -> Course:
    """
    Crée un nouveau cours en utilisant le service IA.
    """
    # Étape 1: Classifier le sujet pour déterminer le type de cours
    course_type = classify_course_topic(course_in.title)

    # Étape 2: Générer le plan d'apprentissage
    learning_plan = generate_learning_plan(course_in.title, course_type)

    db_course = Course(
        title=course_in.title,
        course_type=course_type,
        description=learning_plan.get("overview", f"Un cours sur {course_in.title}"),
        learning_plan_json=learning_plan
    )

    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course