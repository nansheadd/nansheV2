# Fichier: nanshe/backend/app/schemas/level_schema.py
from pydantic import BaseModel
from typing import List
from .knowledge_component_schema import KnowledgeComponent 
from .chapter_schema import Chapter

class Level(BaseModel):
    id: int
    title: str
    level_order: int
    are_chapters_generated: bool
    chapters: List[Chapter] = [] 

    class Config:
        from_attributes = True

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