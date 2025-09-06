# Fichier à créer : nanshe/backend/app/schemas/character_schema.py

from pydantic import BaseModel
from typing import List, Optional

class CharacterBase(BaseModel):
    id: int
    symbol: str
    pronunciation: str

    class Config:
        from_attributes = True

class CharacterSet(BaseModel):
    id: int
    name: str
    characters: List[CharacterBase] = []

    class Config:
        from_attributes = True

class Character(CharacterBase):
    id: int
    chapter_id: int
    strength: Optional[float] = 0.0  # <-- AJOUTER CETTE LIGNE

    class Config:
        from_attributes = True
    