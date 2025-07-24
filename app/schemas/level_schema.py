# Fichier: nanshe/backend/app/schemas/level_schema.py
from pydantic import BaseModel
from typing import List
from .knowledge_component_schema import KnowledgeComponent # On importe le schéma qu'on a déjà créé

class Level(BaseModel):
    """
    Schéma pour renvoyer les données d'un niveau complet,
    incluant son contenu pédagogique.
    """
    id: int
    title: str
    level_order: int
    content_generated: bool
    knowledge_components: List[KnowledgeComponent] = []

    class Config:
        from_attributes = True