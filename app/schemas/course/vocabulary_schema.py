# Fichier à créer : nanshe/backend/app/schemas/vocabulary_schema.py

from pydantic import BaseModel

class VocabularyItem(BaseModel):
    id: int
    term: str
    translation: str
    pronunciation: str | None = None
    example_sentence: str | None = None

    class Config:
        from_attributes = True