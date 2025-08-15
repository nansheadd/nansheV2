# Fichier: nanshe/backend/app/models/user_model.py

from sqlalchemy import Integer, String, Boolean, DateTime, func # type: ignore
from sqlalchemy.orm import Mapped, mapped_column, relationship # type: ignore
from app.db.base import Base
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .user_course_progress_model import UserCourseProgress
    from .user_knowledge_strength_model import UserKnowledgeStrength
    from .user_answer_log_model import UserAnswerLog

class User(Base):
    """
    Modèle SQLAlchemy représentant un utilisateur.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))

    course_progress: Mapped[List["UserCourseProgress"]] = relationship(back_populates="user")
    knowledge_strength: Mapped[List["UserKnowledgeStrength"]] = relationship(back_populates="user")
    answer_logs: Mapped[List["UserAnswerLog"]] = relationship(back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"