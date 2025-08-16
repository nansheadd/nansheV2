# Fichier: backend/app/schemas/chapter_schema.py (CORRIGÉ)
from pydantic import BaseModel
from typing import List, Optional
from .knowledge_component_schema import KnowledgeComponent
from .vocabulary_schema import VocabularyItem
from .grammar_schema import GrammarRule
from .course_schema import CourseInfo


class LevelForChapter(BaseModel):
    id: int
    course: CourseInfo # On imbrique le schéma léger du cours
    class Config:
        from_attributes = True
        
class Chapter(BaseModel):
    id: int
    title: str
    chapter_order: int
    lesson_text: Optional[str] = None
    knowledge_components: List[KnowledgeComponent] = []
    is_accessible: bool = False 

    lesson_status: str
    exercises_status: str
    vocabulary_items: List[VocabularyItem] = []
    grammar_rules: List[GrammarRule] = []
    
    # --- NOUVEAUX CHAMPS ---
    generation_step: Optional[str] = None
    generation_progress: Optional[int] = None
    # ----------------------
    
    level: LevelForChapter

    class Config:
        from_attributes = True

Chapter.model_rebuild()