# Fichier: backend/app/schemas/progress_schema.py
from pydantic import BaseModel
from typing import Dict, Any

class AnswerCreate(BaseModel):
    """
    Schéma pour la soumission d'une réponse par l'utilisateur.
    """
    component_id: int
    user_answer_json: Dict[str, Any] # ex: {"selected_option": 2}

class AnswerResult(BaseModel):
    """
    Schéma pour la réponse de l'API après la soumission d'une réponse.
    """
    is_correct: bool
    feedback: str # Un simple feedback textuel pour commencer