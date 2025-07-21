# Fichier: nanshe/backend/app/schemas/course_schema.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    course_type: str
    visibility: str = "public"
    icon_url: Optional[str] = None
    header_image_url: Optional[str] = None

class CourseCreate(CourseBase):
    """ Schéma utilisé pour la création d'un cours via l'API. """
    pass

class Course(CourseBase):
    """ Schéma utilisé pour renvoyer les données d'un cours via l'API. """
    id: int
    max_level: int
    learning_plan_json: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True