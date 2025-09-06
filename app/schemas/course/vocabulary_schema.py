# Fichier à créer : nanshe/backend/app/schemas/vocabulary_schema.py

from pydantic import BaseModel
from typing import Optional

class VocabularyItem(BaseModel):
    id: int
    term: str
    translation: str
    pronunciation: str | None = None
    example_sentence: str | None = None
    strength: Optional[float] = 0.0

    class Config:
        from_attributes = True