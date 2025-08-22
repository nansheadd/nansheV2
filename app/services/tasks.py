# Fichier à créer : backend/app/services/tasks.py

import logging
from app.db.session import SessionLocal
from app.models.user.user_model import User
from app.models.course.knowledge_graph_model import KnowledgeNode
from app.models.progress.user_course_progress_model import UserCourseProgress

logger = logging.getLogger(__name__)

def generate_node_content_task(node_id: int):
    """
    Tâche de fond pour générer le contenu et les exercices d'un seul nœud.
    Elle gère sa propre session de base de données pour être autonome.
    """
    db = SessionLocal()
    # On importe les services ici, à l'intérieur de la fonction, pour éviter tout risque
    # de dépendance circulaire au démarrage de l'application.
    from app.services.philosophy_course_generator import PhilosophyCourseGenerator

    try:
        node = db.get(KnowledgeNode, node_id)
        if not node:
            logger.error(f"Tâche de contenu annulée : nœud {node_id} non trouvé.")
            return

        course = node.course
        # On retrouve l'utilisateur associé au cours pour le logging des tokens IA
        progress_entry = db.query(UserCourseProgress).filter(UserCourseProgress.course_id == course.id).first()
        if not progress_entry:
            logger.error(f"Impossible de trouver un utilisateur pour le cours {course.id} afin de générer le nœud {node_id}.")
            return
        
        creator = db.get(User, progress_entry.user_id)
        
        # Ce générateur n'a pas besoin de lancer d'autres tâches, donc background_tasks=None
        generator = PhilosophyCourseGenerator(db=db, db_course=course, creator=creator, background_tasks=None)
        
        # On appelle les méthodes spécifiques pour ce nœud
        generator._generate_and_index_node_content(node)

    except Exception as e:
        logger.error(f"Erreur dans la tâche de génération du contenu du nœud {node_id}: {e}", exc_info=True)
    finally:
        db.close()