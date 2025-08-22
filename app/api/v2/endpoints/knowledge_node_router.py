# Fichier: backend/app/api/v2/endpoints/knowledge_node_router.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from app.api.v2.dependencies import get_db
from app.models.course.knowledge_graph_model import KnowledgeNode
from app.schemas.course.knowledge_graph_schema import KnowledgeNode as KnowledgeNodeSchema

router = APIRouter()

@router.get("/{node_id}", response_model=KnowledgeNodeSchema)
def read_knowledge_node(node_id: int, db: Session = Depends(get_db)):
    """
    Récupère le contenu détaillé d'un nœud de connaissance,
    en incluant ses exercices associés de manière optimisée.
    """
    # --- MODIFICATION DE LA STRATÉGIE DE CHARGEMENT ---
    node = db.query(KnowledgeNode).options(
        selectinload(KnowledgeNode.exercises) # Utilisation de selectinload pour la collection
    ).filter(KnowledgeNode.id == node_id).first()
    # -----------------------------------------------
    
    if not node:
        raise HTTPException(status_code=404, detail="Nœud de connaissance non trouvé.")
    return node