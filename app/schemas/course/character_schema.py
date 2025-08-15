# Fichier à créer : nanshe/backend/app/schemas/character_schema.py

from pydantic import BaseModel
from typing import List

class Character(BaseModel):
    id: int
    symbol: str
    pronunciation: str

    class Config:
        from_attributes = True

class CharacterSet(BaseModel):
    id: int
    name: str
    characters: List[Character] = []

    class Config:
        from_attributes = True