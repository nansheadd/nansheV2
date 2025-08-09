# Fichier: backend/app/schemas/personalization_schema.py
from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any

class FormFieldOption(BaseModel):
    value: str
    label: str

class FormField(BaseModel):
    name: str  # Le nom de la clé pour la BDD (ex: "current_level")
    label: str # La question posée à l'utilisateur (ex: "Quel est votre niveau actuel ?")
    type: Literal["select", "text", "textarea"]
    options: Optional[List[FormFieldOption]] = None # Pour le type 'select'

class PersonalizationForm(BaseModel):
    category: str
    fields: List[FormField]

class UserTopicPerformance(BaseModel):
    topic_category: str
    mastery_score: float
    total_attempts: int

    class Config:
        from_attributes = True