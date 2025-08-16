# Fichier: backend/app/models/user_course_progress_model.py (FINAL CORRIGÉ)
from sqlalchemy import Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..user.user_model import User
    from ..course.course_model import Course

class UserCourseProgress(Base):
    """
    Modèle qui suit la progression globale d'un utilisateur dans un cours.
    """
    __tablename__ = "user_course_progress"

    # --- Clé Primaire Composite ---
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), primary_key=True)

    # --- Métriques de Progression ---
    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    
    # --- CORRECTION : AJOUT DES CHAMPS MANQUANTS ---
    current_level_order: Mapped[int] = mapped_column(Integer, default=0)
    current_chapter_order: Mapped[int] = mapped_column(Integer, default=0) # <-- CHAMP AJOUTÉ
    # ---------------------------------------------

    # --- Données de Gamification ---
    rpg_stats_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    last_geshtu_notification_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- Relations ---
    user: Mapped["User"] = relationship(back_populates="course_progress")
    course: Mapped["Course"] = relationship(back_populates="progressions")

    def __repr__(self):
        return f"<UserCourseProgress(user_id={self.user_id}, course_id={self.course_id})>"