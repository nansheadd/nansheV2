# Fichier: nanshe/backend/app/models/progress/user_vocabulary_strength_model.py

from sqlalchemy import Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..user.user_model import User
    from ..course.vocabulary_item_model import VocabularyItem

class UserVocabularyStrength(Base):
    """
    Suit la force de mémorisation d'un utilisateur sur un mot de vocabulaire spécifique (SRS).
    """
    __tablename__ = "user_vocabulary_strengths"

    # --- Clé Primaire Composite ---
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    vocab_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("vocabulary_items.id"), primary_key=True)

    # --- Métriques de Mémorisation (SRS) ---
    strength: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    review_streak: Mapped[int] = mapped_column(Integer, default=0)

    # --- Relations ---
    user: Mapped["User"] = relationship()
    vocabulary_item: Mapped["VocabularyItem"] = relationship()