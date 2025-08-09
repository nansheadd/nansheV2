# Fichier: backend/app/schemas/course_schema.py (VERSION FINALE)
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from .level_schema import Level 

class CourseBase(BaseModel):
    """Contient les champs partagés."""
    title: str
    description: Optional[str] = None
    course_type: str
    visibility: str = "public"
    icon_url: Optional[str] = None
    header_image_url: Optional[str] = None
    model_choice: str # On l'ajoute ici aussi pour être complet

class CourseCreate(BaseModel):
    """Ce que le frontend envoie pour créer un cours."""
    title: str
    model_choice: str = "gemini" # 'gemini' est la valeur par défaut

class Course(CourseBase):
    """Ce que le backend renvoie."""
    id: int
    max_level: int
    learning_plan_json: Optional[Dict[str, Any]] = None
    levels: List['Level'] = [] 
    generation_status: str

    class Config:
        from_attributes = True

Course.model_rebuild()