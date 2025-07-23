# Fichier: nanshe/backend/app/schemas/course_schema.py (CORRIGÉ)
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Ce schéma de base est utilisé par le modèle SQLAlchemy pour la réponse
class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    course_type: str
    visibility: str = "public"
    icon_url: Optional[str] = None
    header_image_url: Optional[str] = None

# Ce schéma est ce que le frontend ENVOIE. Il ne contient que le titre.
class CourseCreate(BaseModel):
    title: str

# Ce schéma est ce que le backend RENVOIE.
class Course(CourseBase):
    id: int
    max_level: int
    learning_plan_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True