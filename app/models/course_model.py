# Fichier: nanshe/backend/app/models/course_model.py

from sqlalchemy import Integer, String, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .user_course_progress_model import UserCourseProgress
    from .knowledge_component_model import KnowledgeComponent
    from .level_model import Level

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

    progressions: Mapped[List["UserCourseProgress"]] = relationship(back_populates="course")
    knowledge_components: Mapped[List["KnowledgeComponent"]] = relationship(back_populates="course")
    levels: Mapped[List["Level"]] = relationship(back_populates="course")

    def __repr__(self):
        return f"<Course(id={self.id}, title='{self.title}')>"