# Fichier à créer : nanshe/backend/app/models/vocabulary_item_model.py

from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chapter_model import Chapter

class VocabularyItem(Base):
    __tablename__ = "vocabulary_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"))
    
    term: Mapped[str] = mapped_column(String(255), nullable=False) # Le mot dans la langue cible (ex: "猫")
    translation: Mapped[str] = mapped_column(String(255), nullable=False) # La traduction (ex: "Chat")
    pronunciation: Mapped[str] = mapped_column(String(255), nullable=True) # La prononciation (ex: "neko")
    example_sentence: Mapped[str] = mapped_column(Text, nullable=True) # Une phrase d'exemple

    chapter: Mapped["Chapter"] = relationship(back_populates="vocabulary_items")