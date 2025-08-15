# Fichier: backend/app/crud/course_crud.py (VERSION MISE À JOUR)
from app.models.user import user_model
from app.models.course import course_model
from app.models.course import level_model
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import not_, select
from app.models.progress import user_course_progress_model
from app.schemas.course import course_schema
from app.core.ai_service import generate_learning_plan, classify_course_topic
from app.services.language_course_generator import LanguageCourseGenerator
from app.services.course_generator import CourseGenerator # <-- IMPORTER LE NOUVEAU SERVICE
import logging

logger = logging.getLogger(__name__)


def create_course_shell(db: Session, course_in: course_schema.CourseCreate, creator: user_model.User) -> course_model.Course:
    # Cette fonction ne change pas
    logger.info(f"Création de la coquille pour le cours '{course_in.title}' pour l'utilisateur {creator.id}")
    db_course = course_model.Course(
        title=course_in.title,
        model_choice=course_in.model_choice,
        generation_status="pending",
        course_type="unknown" # Le type sera déterminé dans la tâche de fond
    )
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

# TÂCHE DE FOND RENOMMÉE
def generate_course_plan_task(db: Session, course_id: int, creator_id: int):
    """
    Tâche de fond qui classifie le cours, puis appelle le générateur approprié.
    """
    logger.info(f"Tâche de fond : Démarrage de la planification pour le cours ID: {course_id}")
    db_course = db.get(course_model.Course, course_id)
    if not db_course:
        logger.error(f"Tâche annulée : cours {course_id} non trouvé.")
        return

    try:
        db_course.generation_status = "generating"
        db.commit()

        # Étape 1 : Classifier le sujet pour décider de la route à prendre
        course_type = classify_course_topic(title=db_course.title, model_choice=db_course.model_choice)
        db_course.course_type = course_type
        db.commit()
        
        creator = db.get(user_model.User, creator_id)
        course_in = course_schema.CourseCreate(title=db_course.title, model_choice=db_course.model_choice)

        # Étape 2 : Aiguillage vers le bon générateur
        
        if course_type == 'langue':
            logger.info(f"Cours de langue détecté. Utilisation de LanguageCourseGenerator pour le cours ID: {course_id}")
            # --- CORRECTION DE L'APPEL ---
            # On passe l'objet db_course directement, on ne crée plus de course_in
            lang_generator = LanguageCourseGenerator(db=db, db_course=db_course, creator=creator)
            lang_generator.generate_full_course_scaffold()
        else:
            logger.info(f"Cours standard détecté. Utilisation du générateur générique pour le cours ID: {course_id}")
            # On utilise l'ancienne logique pour les autres types de cours
            generate_generic_course_plan(db, db_course, creator)

    except Exception as e:
        logger.error(f"Erreur majeure lors de la génération du plan pour le cours ID {course_id}: {e}", exc_info=True)
        db.rollback()
        db_course_to_fail = db.get(course_model.Course, course_id)
        if db_course_to_fail:
            db_course_to_fail.generation_status = "failed"
            db.commit()


def generate_generic_course_plan(db: Session, db_course: course_model.Course, creator: user_model.User):
    """
    Contient l'ancienne logique de génération de plan pour les cours non linguistiques.
    """
    learning_plan = generate_learning_plan(
        title=db_course.title, course_type=db_course.course_type, model_choice=db_course.model_choice
    )
    db_course.description = learning_plan.get("overview", f"Un cours sur {db_course.title}")
    db_course.learning_plan_json = learning_plan
    
    levels_data = learning_plan.get("levels", [])
    for i, level_data in enumerate(levels_data):
        db_level = level_model.Level(
            course_id=db_course.id,
            title=level_data.get("level_title", f"Niveau {i+1}"),
            level_order=i,
            are_chapters_generated=False # Le contenu sera généré en JIT
        )
        db.add(db_level)

    creator_progress = user_course_progress_model.UserCourseProgress(
        user_id=creator.id, course_id=db_course.id, current_level_order=0
    )
    db.add(creator_progress)
    db_course.generation_status = "completed"
    db.commit()

def generate_course_content_task(db: Session, course_id: int, creator_id: int):
    """
    Tâche de fond pour générer UNIQUEMENT le plan initial d'un cours (niveaux).
    """
    logger.info(f"Tâche de fond JIT : Démarrage du plan pour le cours ID: {course_id}")
    db_course = db.get(course_model.Course, course_id)
    if not db_course:
        logger.error(f"Tâche JIT annulée : cours {course_id} non trouvé.")
        return

    try:
        # La logique de génération du plan est correcte ici
        course_type = classify_course_topic(title=db_course.title, model_choice=db_course.model_choice)
        learning_plan = generate_learning_plan(
            title=db_course.title,
            course_type=course_type,
            model_choice=db_course.model_choice
        )

        db_course.description = learning_plan.get("overview", f"Un cours sur {db_course.title}")
        db_course.course_type = course_type
        db_course.learning_plan_json = learning_plan
        
        # On crée les niveaux comme des coquilles vides
        levels_data = learning_plan.get("levels", [])
        for i, level_data in enumerate(levels_data):
            db_level = level_model.Level(
                course_id=db_course.id,
                title=level_data.get("level_title", f"Niveau {i+1}"),
                level_order=i,
                are_chapters_generated=False # Explicitement non générés
            )
            db.add(db_level)

        # Inscrire le créateur et finaliser
        creator_progress = user_course_progress_model.UserCourseProgress(
            user_id=creator_id, course_id=db_course.id, current_level_order=0
        )
        db.add(creator_progress)

        db_course.generation_status = "completed" # Le plan est complété, pas le cours entier
        db.commit()
        logger.info(f"Tâche de fond JIT : Plan du cours ID: {course_id} terminé.")

    except Exception as e:
        logger.error(f"Erreur lors de la génération du plan JIT pour le cours ID {course_id}: {e}")
        db.rollback()
        db_course.generation_status = "failed"
        db.commit()


def create_course(db: Session, course_in: course_schema.CourseCreate, creator: user_model.User) -> course_model.Course:
    """
    Crée une entrée de cours "brouillon" SANS lancer la génération directement.
    La génération sera gérée par la tâche de fond via le routeur.
    Note: Dans cette nouvelle architecture, cette fonction n'est plus directement responsable de la création
    en BDD, car le générateur le fait. On la garde pour la structure mais elle pourrait être fusionnée.
    Pour l'instant, on la laisse conceptuellement.
    
    NOUVELLE APPROCHE : Cette fonction n'est plus nécessaire car le générateur
    gère la création initiale. On la laisse vide pour l'instant pour ne pas casser le routeur,
    mais elle devrait être supprimée à terme.
    """
    # La création est maintenant gérée par la première étape du CourseGenerator.
    # On pourrait retourner un objet conceptuel si nécessaire.
    # Pour l'instant, le routeur a juste besoin de lancer la tâche.
    pass

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