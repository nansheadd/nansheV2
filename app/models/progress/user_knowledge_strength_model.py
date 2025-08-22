# Fichier: nanshe/backend/app/models/user_knowledge_strength_model.py

from sqlalchemy import Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..user.user_model import User
    from ..course.knowledge_graph_model import KnowledgeComponent

class UserKnowledgeStrength(Base):
    """
    Modèle qui suit la maîtrise d'un utilisateur sur une brique de savoir.
    C'est le moteur du système de répétition espacée (SRS).
    """
    __tablename__ = "user_knowledge_strengths"

    # --- Clé Primaire Composite ---
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    component_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_components.id"), primary_key=True)

    # --- Métriques de Mémorisation (SRS) ---
    strength: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    review_streak: Mapped[int] = mapped_column(Integer, default=0)

    # --- Métriques de Métacognition ---
    last_confidence_rating: Mapped[Optional[int]] = mapped_column(Integer)

    # --- Relations ---
    user: Mapped["User"] = relationship(back_populates="knowledge_strength")
    knowledge_component: Mapped["KnowledgeComponent"] = relationship(back_populates="user_strengths")

    def __repr__(self):
        return f"<UserKnowledgeStrength(user_id={self.user_id}, component_id={self.component_id})>"