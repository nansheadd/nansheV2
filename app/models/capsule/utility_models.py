from sqlalchemy import Integer, String, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user.user_model import User
    from .capsule_model import Capsule

class UserCapsuleEnrollment(Base):
    __tablename__ = "user_capsule_enrollments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    capsule_id: Mapped[int] = mapped_column(Integer, ForeignKey("capsules.id"), index=True)
    
    user: Mapped["User"] = relationship(back_populates="enrollments")
    capsule: Mapped["Capsule"] = relationship(back_populates="user_enrollments")

class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))

class UserCapsuleProgress(Base):
    __tablename__ = "user_capsule_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    capsule_id: Mapped[int] = mapped_column(Integer, ForeignKey("capsules.id"), index=True)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id"), index=True)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    
    capsule: Mapped["Capsule"] = relationship(back_populates="user_progress_entries")
    skill: Mapped["Skill"] = relationship()
    user: Mapped["User"] = relationship(back_populates="capsule_progress")