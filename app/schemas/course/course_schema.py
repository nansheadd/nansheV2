# Fichier: backend/app/schemas/course_schema.py (VERSION FINALE)
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from .character_schema import CharacterSet 



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


class CourseInfo(BaseModel):
    course_type: str
    class Config:
        from_attributes = True

class Course(CourseBase):
    """Ce que le backend renvoie."""
    id: int
    max_level: int
    learning_plan_json: Optional[Dict[str, Any]] = None
    levels: List['Level'] = [] 
    generation_status: str
    character_sets: List[CharacterSet] = []

    # --- NOUVEAUX CHAMPS ---
    generation_step: Optional[str] = None
    generation_progress: Optional[int] = None
    # ----------------------

    levels: List['Level'] = []

    class Config:
        from_attributes = True


class CourseReadMinimal(BaseModel):
    """
    Schéma de réponse minimal pour la création de cours en tâche de fond (réponse 202).
    Fournit juste assez d'infos pour que le frontend puisse rediriger et suivre la génération.
    """
    id: int
    title: str
    generation_status: str

    class Config:
        from_attributes = True

class CourseInfo(BaseModel):
    course_type: str
    class Config:
        from_attributes = True

        
from .level_schema import Level
Course.model_rebuild()