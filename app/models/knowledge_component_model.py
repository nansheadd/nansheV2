# Fichier: nanshe/backend/app/models/knowledge_component_model.py

from sqlalchemy import Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .course_model import Course
    from .user_knowledge_strength_model import UserKnowledgeStrength
    from .user_answer_log_model import UserAnswerLog

class KnowledgeComponent(Base):
    """
    Modèle SQLAlchemy représentant une brique de savoir atomique.
    C'est l'unité de base de l'apprentissage et de la gamification.
    """
    __tablename__ = "knowledge_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # --- Liens et Catégorisation ---
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False) # La catégorie pour les stats RPG

    # --- Contenu Pédagogique ---
    title: Mapped[str] = mapped_column(String(255), nullable=False) # Ex: "Le Syllogisme d'Aristote"
    # Le contenu généré par l'IA (leçon, quiz, etc.)
    content_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # --- Paramètres de Difficulté (inspirés par la science) ---
    component_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'qcm', 'fill_in_the_blank', etc.
    bloom_level: Mapped[str] = mapped_column(String(50)) # 'remember', 'apply', 'create', etc.

    # --- Relations ---
    course: Mapped["Course"] = relationship(back_populates="knowledge_components")
    user_strengths: Mapped[List["UserKnowledgeStrength"]] = relationship(back_populates="knowledge_component")
    user_answers: Mapped[List["UserAnswerLog"]] = relationship(back_populates="knowledge_component")

    def __repr__(self):
        return f"<KnowledgeComponent(id={self.id}, title='{self.title}')>"