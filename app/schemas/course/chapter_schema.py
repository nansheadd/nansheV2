# Fichier: backend/app/schemas/chapter_schema.py (VERSION MISE À JOUR)
from pydantic import BaseModel
from typing import List, Optional
from .knowledge_component_schema import KnowledgeComponent
from .vocabulary_schema import VocabularyItem
from .grammar_schema import GrammarRule
from .character_schema import Character
from .course_schema import CourseInfo

class LevelForChapter(BaseModel):
    id: int
    course: CourseInfo
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
    characters: List[Character] = []
    vocabulary: List[VocabularyItem] = []
    
    generation_step: Optional[str] = None
    generation_progress: Optional[int] = None

    # --- NOUVEAU CHAMP ---
    is_theoretical: bool
    # -------------------
    
    level: LevelForChapter

    class Config:
        from_attributes = True

Chapter.model_rebuild()
