# Fichier: backend/app/api/v2/endpoints/knowledge_node_router.py

import logging # <-- AJOUT : Pour pouvoir utiliser logger.info
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, selectinload

from app.api.v2.dependencies import get_db
from app.models.course.knowledge_graph_model import KnowledgeNode
from app.schemas.course.knowledge_graph_schema import KnowledgeNode as KnowledgeNodeSchema
from app.services.tasks import generate_programming_node_content_task

router = APIRouter()
logger = logging.getLogger(__name__) # <-- AJOUT : Initialisation du logger

@router.get("/{node_id}", response_model=KnowledgeNodeSchema)
def read_knowledge_node(
    node_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Récupère le contenu détaillé d'un nœud de connaissance,
    en incluant ses exercices associés de manière optimisée.
    Déclenche la génération de contenu JIT si nécessaire.
    """
    node = db.query(KnowledgeNode).options(
        selectinload(KnowledgeNode.exercises),
        selectinload(KnowledgeNode.course) # <-- S'assurer que la relation 'course' est chargée
    ).filter(KnowledgeNode.id == node_id).first()
    
    if not node:
        raise HTTPException(status_code=404, detail="Nœud de connaissance non trouvé.")
    
    # + =================================================================
    # + DÉCLENCHEUR JIT (maintenant fonctionnel)
    # + =================================================================
    # Si le nœud a bien un cours associé, que ce cours est de type "PROGRAMMING"
    # ET que le contenu principal du nœeud n'a pas encore été généré...
    if node.course and node.course.course_type == "PROGRAMMING" and not node.content_json:
        logger.info(f"Déclenchement de la génération JIT pour le nœud ID {node.id}")
        # ... on lance la tâche de génération en arrière-plan.
        background_tasks.add_task(generate_programming_node_content_task, node.id)
        # La réponse est renvoyée immédiatement à l'utilisateur, sans attendre.
    
    return node