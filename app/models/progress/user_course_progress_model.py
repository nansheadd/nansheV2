# Fichier: backend/app/models/progress/user_course_progress_model.py

from sqlalchemy import Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..user.user_model import User
    from ..capsule.capsule_model import Capsule # <-- MODIFIÉ

class UserCourseProgress(Base):
    __tablename__ = "user_course_progress"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
    # --- MODIFIÉ : On lie à la table 'capsules' ---
    capsule_id: Mapped[int] = mapped_column(Integer, ForeignKey("capsules.id"), primary_key=True)

    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    current_level_order: Mapped[int] = mapped_column(Integer, default=1) # Ordre commence à 1
    current_chapter_order: Mapped[int] = mapped_column(Integer, default=1)
    
    rpg_stats_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    last_geshtu_notification_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- MODIFIÉ : La relation pointe maintenant vers Capsule ---
    user: Mapped["User"] = relationship() # La relation avec User ne change pas
    capsule: Mapped["Capsule"] = relationship(back_populates="course_progress")

    def __repr__(self):
        return f"<UserCourseProgress(user_id={self.user_id}, capsule_id={self.capsule_id})>"