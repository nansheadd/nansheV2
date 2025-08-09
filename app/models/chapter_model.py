# Fichier: backend/app/models/chapter_model.py (CORRIGÉ)
from sqlalchemy import Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .level_model import Level
    from .knowledge_component_model import KnowledgeComponent

class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter_order: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_text: Mapped[str] = mapped_column(Text, nullable=True)

    # --- CHAMPS DE STATUT MIS À JOUR ---
    # On remplace les booléens par des statuts plus fins
    lesson_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    exercises_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    # ------------------------------------

    level_id: Mapped[int] = mapped_column(Integer, ForeignKey("levels.id"))
    level: Mapped["Level"] = relationship(back_populates="chapters")
    knowledge_components: Mapped[List["KnowledgeComponent"]] = relationship(back_populates="chapter")