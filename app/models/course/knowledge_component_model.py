# Fichier: backend/app/models/course/knowledge_component_model.py (FINAL MIS À JOUR)
from sqlalchemy import Integer, String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .chapter_model import Chapter
    from ..progress.user_knowledge_strength_model import UserKnowledgeStrength

class KnowledgeComponent(Base):
    __tablename__ = "knowledge_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- NOUVELLE TAXONOMIE ---
    # Remplace l'ancien champ "category" pour une classification plus structurée.
    domain: Mapped[str] = mapped_column(String(100), index=True, nullable=True)
    area: Mapped[str] = mapped_column(String(100), index=True, nullable=True)
    skill: Mapped[str] = mapped_column(String(100), index=True, nullable=True)
    # --------------------------

    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bloom_level: Mapped[str] = mapped_column(String(50))
    content_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # --- Relations ---
    chapter: Mapped["Chapter"] = relationship(back_populates="knowledge_components")
    
    # On rend les relations plus explicites pour casser les cycles de dépendance
    user_strengths: Mapped[List["UserKnowledgeStrength"]] = relationship(
        "UserKnowledgeStrength", back_populates="knowledge_component", cascade="all, delete-orphan"
    )


    def __repr__(self):
        return f"<KnowledgeComponent(id={self.id}, title='{self.title}')>"