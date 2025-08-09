# Fichier: backend/app/schemas/knowledge_component_schema.py
from pydantic import BaseModel
from typing import Dict, Any, Optional

class UserAnswer(BaseModel):
    is_correct: bool
    user_answer_json: Dict[str, Any]
    class Config: from_attributes = True

class KnowledgeComponent(BaseModel):
    id: int
    title: str
    category: str
    component_type: str
    content_json: Dict[str, Any]
    user_answer: Optional[UserAnswer] = None
    chapter_id: int # <-- AJOUTER CETTE LIGNE

    class Config:
        from_attributes = True