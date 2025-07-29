# Fichier: backend/app/models/knowledge_component_model.py

from sqlalchemy import Integer, String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .chapter_model import Chapter
    from .user_knowledge_strength_model import UserKnowledgeStrength
    from .user_answer_log_model import UserAnswerLog

class KnowledgeComponent(Base):
    """
    Modèle SQLAlchemy représentant un exercice interactif unique.
    C'est le composant de base pour tester la connaissance.
    """
    __tablename__ = "knowledge_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # --- Lien vers le Parent ---
    # Un exercice appartient maintenant à un chapitre.
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"))
    
    # --- Métadonnées de l'Exercice ---
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'qcm', 'fill_in_the_blank', etc.
    bloom_level: Mapped[str] = mapped_column(String(50)) # 'remember', 'apply', 'create', etc.

    # --- Contenu de l'Exercice ---
    # Stocke la question, les options, la leçon associée, etc.
    content_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # --- Relations ---
    chapter: Mapped["Chapter"] = relationship(back_populates="knowledge_components")
    
    # Relations avec les données de l'utilisateur
    user_strengths: Mapped[List["UserKnowledgeStrength"]] = relationship(back_populates="knowledge_component")
    user_answers: Mapped[List["UserAnswerLog"]] = relationship(back_populates="knowledge_component")

    def __repr__(self):
        return f"<KnowledgeComponent(id={self.id}, title='{self.title}')>"