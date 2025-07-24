# Fichier: nanshe/backend/app/crud/level_crud.py (VERSION CORRECTE)
from sqlalchemy.orm import Session
from app.models import level_model, knowledge_component_model
from app.core.ai_service import generate_level_content
import logging

logger = logging.getLogger(__name__)

def get_level_content(db: Session, course_id: int, level_order: int):
    """
    Récupère un niveau et son contenu. S'il n'a pas encore été généré,
    il est créé à la volée.
    """
    # 1. Trouver le niveau dans la base de données
    level = db.query(level_model.Level).filter(
        level_model.Level.course_id == course_id,
        level_model.Level.level_order == level_order
    ).first()

    if not level:
        return None # Niveau non trouvé

    # 2. Vérifier si le contenu a déjà été généré
    if not level.content_generated:
        logger.info(f"Contenu non trouvé pour le niveau '{level.title}'. Génération en cours...")
        
        # 3. Appeler l'IA pour générer le contenu
        components_data = generate_level_content(level.title, level.course.course_type)

        # 4. Sauvegarder les nouvelles briques de savoir
        for data in components_data:
            if "error" not in data:
                component = knowledge_component_model.KnowledgeComponent(
                    level_id=level.id, # On lie à l'ID du niveau
                    title=data.get("title"),
                    category=data.get("category"),
                    component_type=data.get("component_type"),
                    bloom_level=data.get("bloom_level"),
                    content_json=data.get("content_json")
                )
                db.add(component)
        
        level.content_generated = True # On marque le niveau comme généré
        db.add(level)
        db.commit()
        db.refresh(level) # On rafraîchit pour charger les nouveaux composants

    return level