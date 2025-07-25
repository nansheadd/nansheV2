# Fichier: nanshe/backend/app/models/course_model.py (CORRECTED)

from sqlalchemy import Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .user_course_progress_model import UserCourseProgress
    from .level_model import Level # We need to know about levels

class Course(Base):
    """
    Modèle SQLAlchemy représentant un cours.
    """
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    icon_url: Mapped[Optional[str]] = mapped_column(String(2048))
    header_image_url: Mapped[Optional[str]] = mapped_column(String(2048))
    course_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    visibility: Mapped[str] = mapped_column(String(50), default="public", nullable=False)
    max_level: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    learning_plan_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # --- Relations ---
    progressions: Mapped[List["UserCourseProgress"]] = relationship(back_populates="course")

    # This is the correct relationship now: A course has a list of levels.
    levels: Mapped[List["Level"]] = relationship(back_populates="course")

    # THE INCORRECT RELATIONSHIP HAS BEEN REMOVED

    def __repr__(self):
        return f"<Course(id={self.id}, title='{self.title}')>"