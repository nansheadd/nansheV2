# Fichier: backend/app/schemas/chapter_schema.py (CORRIGÉ)
from pydantic import BaseModel
from typing import List, Optional
from .knowledge_component_schema import KnowledgeComponent

class Chapter(BaseModel):
    id: int
    title: str
    chapter_order: int
    lesson_text: Optional[str] = None
    knowledge_components: List[KnowledgeComponent] = []
    is_accessible: bool = False 

    # --- NOUVEAUX CHAMPS ---
    lesson_status: str
    exercises_status: str
    # ----------------------
    
    # On ajoute le level_id pour pouvoir remonter dans la navigation du frontend
    level_id: int

    class Config:
        from_attributes = True