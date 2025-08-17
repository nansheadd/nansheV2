# Fichier: backend/app/models/chapter_model.py (VERSION MISE À JOUR)
from sqlalchemy import Integer, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .level_model import Level
    from .knowledge_component_model import KnowledgeComponent
    from .vocabulary_item_model import VocabularyItem
    from .grammar_rule_model import GrammarRule 

class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter_order: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_text: Mapped[str] = mapped_column(Text, nullable=True)

    lesson_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    exercises_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    
    generation_step: Mapped[Optional[str]] = mapped_column(String(255))
    generation_progress: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # --- NOUVEAU CHAMP POUR LE TYPE DE CHAPITRE ---
    is_theoretical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ---------------------------------------------

    level_id: Mapped[int] = mapped_column(Integer, ForeignKey("levels.id"))
    level: Mapped["Level"] = relationship(back_populates="chapters")
    knowledge_components: Mapped[List["KnowledgeComponent"]] = relationship(back_populates="chapter")

    vocabulary_items: Mapped[List["VocabularyItem"]] = relationship(back_populates="chapter")
    grammar_rules: Mapped[List["GrammarRule"]] = relationship(back_populates="chapter")
