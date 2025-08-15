# Fichier: backend/app/models/user_topic_performance_model.py (FINAL CORRIGÉ)
from sqlalchemy import Integer, String, DateTime, ForeignKey, func, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..user.user_model import User
    from ..course.course_model import Course

class UserTopicPerformance(Base):
    """
    Modèle qui agrège les performances d'un utilisateur sur un sujet (catégorie)
    spécifique au sein d'un cours.
    """
    __tablename__ = "user_topic_performances"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), primary_key=True)
    topic_category: Mapped[str] = mapped_column(String(255), primary_key=True)

    correct_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incorrect_answers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # --- CORRECTION ICI ---
    # On ajoute `server_default=func.now()` pour gérer la création de la ligne.
    # `onupdate` gérera les mises à jour ultérieures.
    last_practiced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(),
        nullable=False
    )
    # --------------------

    # Relations
    user: Mapped["User"] = relationship()
    course: Mapped["Course"] = relationship()