# Fichier: backend/app/models/course/vocabulary_item_model.py
from sqlalchemy import Integer, String, ForeignKey, Text # Make sure ForeignKey is imported
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..progress.user_vocabulary_strenght_model import UserVocabularyStrength
    from .chapter_model import Chapter # Import Chapter

class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # V-- AJOUTEZ CETTE COLONNE --V
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"), nullable=False)

    word: Mapped[str] = mapped_column(String, nullable=False)
    pinyin: Mapped[Optional[str]] = mapped_column(String)
    translation: Mapped[str] = mapped_column(String)
    example_sentence: Mapped[Optional[str]] = mapped_column(Text)


    # --- Relations ---
    chapter: Mapped["Chapter"] = relationship(back_populates="vocabulary")
    user_strengths: Mapped[List["UserVocabularyStrength"]] = relationship(back_populates="vocabulary_item", cascade="all, delete-orphan")