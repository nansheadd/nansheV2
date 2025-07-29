# Fichier: backend/app/models/chapter_model.py
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

    # Le contenu de la leçon, généré par l'IA
    lesson_text: Mapped[str] = mapped_column(Text, nullable=True)

    # Statuts de génération
    is_lesson_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    are_exercises_generated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Lien vers le niveau parent
    level_id: Mapped[int] = mapped_column(Integer, ForeignKey("levels.id"))
    level: Mapped["Level"] = relationship(back_populates="chapters")

    # Un chapitre a plusieurs exercices (KnowledgeComponents)
    knowledge_components: Mapped[List["KnowledgeComponent"]] = relationship(back_populates="chapter")