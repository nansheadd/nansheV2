# Fichier: nanshe/backend/app/models/user_answer_log_model.py

from sqlalchemy import Integer, Boolean, JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .user_model import User
    from .knowledge_component_model import KnowledgeComponent

class UserAnswerLog(Base):
    """
    Modèle SQLAlchemy qui enregistre chaque réponse d'un utilisateur
    à un exercice lié à une brique de savoir.
    C'est l'historique brut pour l'analyse de Geshtu.
    """
    __tablename__ = "user_answer_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # --- Qui a répondu à quoi ? ---
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    component_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_components.id"), nullable=False)

    # --- Quand et comment ? ---
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    
    # --- La réponse elle-même ---
    # On stocke la réponse de l'utilisateur au format JSON pour une flexibilité maximale.
    # Pour un QCM, ça pourrait être {"selected_option": 2}.
    # Pour un texte à trous, {"filled_blanks": ["mot1", "mot2"]}.
    user_answer_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    # --- Relations ---
    user: Mapped["User"] = relationship(back_populates="answer_logs")
    knowledge_component: Mapped["KnowledgeComponent"] = relationship(back_populates="user_answers")

    def __repr__(self):
        return f"<UserAnswerLog(user_id={self.user_id}, component_id={self.component_id}, correct={self.is_correct})>"