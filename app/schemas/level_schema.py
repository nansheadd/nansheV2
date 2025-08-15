# Fichier à modifier : nanshe/backend/app/schemas/level_schema.py

from pydantic import BaseModel
from typing import List
from .course_schema import CourseInfo
# On retire l'import de Chapter car on va aussi utiliser une référence anticipée

class CourseInfo(BaseModel):
    course_type: str
    class Config:
        from_attributes = True

class Level(BaseModel):
    id: int
    title: str
    level_order: int
    are_chapters_generated: bool
    course_id: int
    course: CourseInfo
    chapters: List['Chapter'] = [] # On utilise une référence anticipée
    is_accessible: bool = False

    class Config:
        from_attributes = True


# --- AJOUT CRUCIAL ---
from .chapter_schema import Chapter
Level.model_rebuild()