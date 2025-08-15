# Fichier à créer : nanshe/backend/app/schemas/grammar_schema.py

from pydantic import BaseModel

class GrammarRule(BaseModel):
    id: int
    rule_name: str
    explanation: str
    example_sentence: str | None = None

    class Config:
        from_attributes = True