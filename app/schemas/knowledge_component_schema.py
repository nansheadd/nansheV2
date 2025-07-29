# Fichier: nanshe/backend/app/schemas/knowledge_component_schema.py
from pydantic import BaseModel
from typing import Dict, Any, Optional


# On a besoin d'un schéma pour la réponse de l'utilisateur
class UserAnswer(BaseModel):
    is_correct: bool
    user_answer_json: Dict[str, Any]
    class Config: from_attributes = True

class KnowledgeComponent(BaseModel):
    """
    Schéma pour renvoyer les données d'une brique de savoir via l'API.
    """
    id: int
    title: str
    category: str
    component_type: str
    content_json: Dict[str, Any]
    user_answer: Optional[UserAnswer] = None

    class Config:
        from_attributes = True