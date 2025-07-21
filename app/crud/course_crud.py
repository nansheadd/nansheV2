# Fichier: nanshe/backend/app/crud/course_crud.py
from sqlalchemy.orm import Session
from app.models.course_model import Course
from app.schemas.course_schema import CourseCreate

def create_course(db: Session, course: CourseCreate) -> Course:
    """
    Crée un nouveau cours dans la base de données.
    Pour ce MVP, le plan d'apprentissage est généré en dur.
    """
    # --- Ceci est notre simulation de la réponse de l'IA ---
    dummy_learning_plan = {
        "overview": "Ce cours vous introduira aux concepts fondamentaux de la philosophie.",
        "rpg_stats_schema": {
            "Logique": 10,
            "Rhétorique": 10,
            "Histoire": 5
        },
        "levels": [
            {"level_title": "Introduction à Socrate", "category": "Philosophie Antique"},
            {"level_title": "Platon et la Théorie des Idées", "category": "Métaphysique"},
            {"level_title": "L'Éthique d'Aristote", "category": "Éthique"}
        ]
    }
    # ---------------------------------------------------------

    db_course = Course(
        title=course.title,
        description=course.description,
        course_type=course.course_type,
        visibility=course.visibility,
        icon_url=course.icon_url,
        header_image_url=course.header_image_url,
        learning_plan_json=dummy_learning_plan
    )

    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course