# Fichier à créer : nanshe/backend/app/models/character_model.py

from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .course_model import Course

# Ce modèle représente un ensemble de caractères, comme "Hiragana" ou "Alphabet Cyrillique"
class CharacterSet(Base):
    __tablename__ = "character_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"))
    name: Mapped[str] = mapped_column(String(100), nullable=False) # Ex: "Hiragana"

    course: Mapped["Course"] = relationship(back_populates="character_sets")
    characters: Mapped[List["Character"]] = relationship(back_populates="character_set")

# Ce modèle représente un caractère individuel
class Character(Base):
    __tablename__ = "characters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    character_set_id: Mapped[int] = mapped_column(Integer, ForeignKey("character_sets.id"))
    
    symbol: Mapped[str] = mapped_column(String(10), nullable=False) # Ex: "あ"
    pronunciation: Mapped[str] = mapped_column(String(50), nullable=False) # Ex: "a"

    character_set: Mapped["CharacterSet"] = relationship(back_populates="characters")