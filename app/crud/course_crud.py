# Fichier: nanshe/backend/app/crud/course_crud.py (CORRIGÉ)
from sqlalchemy.orm import Session
from app.models.course_model import Course
from app.schemas.course_schema import CourseCreate # On importe le bon schéma

def create_course(db: Session, course_in: CourseCreate) -> Course:
    """
    Crée un nouveau cours.
    1. (Simulé) Détermine le type de cours à partir du titre.
    2. (Simulé) Génère le plan d'apprentissage.
    """

    # Simulation de la classification par IA
    title_lower = course_in.title.lower()
    course_type = "general"
    if "philosophie" in title_lower:
        course_type = "philosophy"
    elif "math" in title_lower:
        course_type = "math"
    elif "japonais" in title_lower:
        course_type = "language"

    # Simulation de la génération du plan par IA
    dummy_learning_plan = {
        "overview": f"Un cours généré par IA sur {course_in.title}.",
        "rpg_stats_schema": {"Compréhension": 0, "Mémorisation": 0},
        "levels": [
            {"level_title": f"Introduction à {course_in.title}", "category": "Fondamentaux"},
            {"level_title": "Concepts Avancés", "category": "Approfondissement"}
        ]
    }

    db_course = Course(
        title=course_in.title,
        course_type=course_type, # On utilise le type déterminé
        learning_plan_json=dummy_learning_plan,
        description=f"Un cours sur {course_in.title}" # On ajoute une description par défaut
    )

    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course