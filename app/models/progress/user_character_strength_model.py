# Fichier: backend/app/models/progress/user_character_strength_model.py

from sqlalchemy import Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..user.user_model import User
    from ..course.character_model import Character

class UserCharacterStrength(Base):
    """
    Suit la force de mémorisation d'un utilisateur sur un caractère spécifique (SRS).
    """
    __tablename__ = "user_character_strengths"

    # --- Clé Primaire Composite ---
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    # LA CORRECTION PRINCIPALE EST ICI: "characters.id" est le nom correct de la table
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("characters.id"), primary_key=True)

    # --- Métriques de Mémorisation (SRS) ---
    strength: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    review_streak: Mapped[int] = mapped_column(Integer, default=0)

    # --- Relations Bidirectionnelles ---
    user: Mapped["User"] = relationship(back_populates="character_strengths")
    character: Mapped["Character"] = relationship(back_populates="user_strengths")