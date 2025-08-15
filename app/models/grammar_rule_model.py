# Fichier à créer : nanshe/backend/app/models/grammar_rule_model.py

from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chapter_model import Chapter

class GrammarRule(Base):
    __tablename__ = "grammar_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"))

    rule_name: Mapped[str] = mapped_column(String(255), nullable=False) # Ex: "La particule は (wa)"
    explanation: Mapped[str] = mapped_column(Text, nullable=False) # L'explication de la règle
    example_sentence: Mapped[str] = mapped_column(Text, nullable=True)

    chapter: Mapped["Chapter"] = relationship(back_populates="grammar_rules")