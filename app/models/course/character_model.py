# Fichier: backend/app/models/course/character_model.py (VERSION FINALE ET CORRIGÉE)

from sqlalchemy import Integer, String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, Optional, TYPE_CHECKING

# Use TYPE_CHECKING blocks to prevent circular import errors at runtime
if TYPE_CHECKING:
    from ..progress.user_character_strength_model import UserCharacterStrength
    from .chapter_model import Chapter
    from .course_model import Course

class CharacterSet(Base):
    """
    Represents a set of characters (e.g., Hiragana, Katakana) for a language course.
    """
    __tablename__ = "character_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Foreign Key to the Course model
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    
    # --- Relationships ---
    # The Course this set belongs to
    course: Mapped["Course"] = relationship(back_populates="character_sets")
    
    # The list of Characters in this set
    characters: Mapped[List["Character"]] = relationship(
        back_populates="character_set", 
        cascade="all, delete-orphan"
    )

class Character(Base):
    """
    Represents a single character (e.g., 'あ', 'a', '你好') in a course.
    """
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # --- Foreign Keys ---
    # This is the crucial link that was missing or incorrect.
    # It explicitly tells SQLAlchemy how a Character connects to a CharacterSet.
    character_set_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("character_sets.id"), nullable=True)
    
    # A character can also be introduced in a specific chapter
    chapter_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("chapters.id"), nullable=True)
    
    # --- Character Data ---
    character: Mapped[str] = mapped_column(String, nullable=False)
    pinyin: Mapped[Optional[str]] = mapped_column(String)
    meaning: Mapped[Optional[str]] = mapped_column(String)
    
    # --- Relationships ---
    # The CharacterSet this character belongs to
    character_set: Mapped[Optional["CharacterSet"]] = relationship(back_populates="characters")

    # The Chapter this character is introduced in
    chapter: Mapped[Optional["Chapter"]] = relationship(back_populates="characters")
    
    # The strength/progress for each user on this character
    user_strengths: Mapped[List["UserCharacterStrength"]] = relationship(
        back_populates="character", 
        cascade="all, delete-orphan"
    )