import enum
from sqlalchemy import Integer, String, ForeignKey, JSON, Boolean, Enum as EnumSQL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional, Dict, Any, TYPE_CHECKING

from app.db.base_class import Base

# --- Imports relatifs pour lier les modèles ---
if TYPE_CHECKING:
    from app.models.user.user_model import User
    from .granule_model import Granule
    from .language_roadmap_model import LanguageRoadmap
    
    # --- CORRECTION FINALE ---
    # On supprime les imports incorrects et on garde UNIQUEMENT
    # ceux qui proviennent de utility_models.py pour la progression.
    from app.models.progress.user_course_progress_model import UserCourseProgress

    from .utility_models import UserCapsuleEnrollment, UserCapsuleProgress


class GenerationStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class Capsule(Base):
    """Représente le cours ou le module d'apprentissage global."""
    __tablename__ = "capsules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    area: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    main_skill: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    learning_plan_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )

    # Correction: le nom de la colonne est 'creator_id'
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    generation_status: Mapped[GenerationStatus] = mapped_column(
        EnumSQL(GenerationStatus, name="generation_status_enum"), 
        default=GenerationStatus.PENDING, 
        nullable=False
    )

    
    # --- Relations ---
    creator: Mapped["User"] = relationship(back_populates="created_capsules")
    granules: Mapped[List["Granule"]] = relationship(
        back_populates="capsule", cascade="all, delete-orphan"
    )
    roadmaps: Mapped[List["LanguageRoadmap"]] = relationship(back_populates="capsule", cascade="all, delete-orphan")

    user_enrollments: Mapped[List["UserCapsuleEnrollment"]] = relationship(back_populates="capsule")
    progressions: Mapped[List["UserCapsuleProgress"]] = relationship(back_populates="capsule")

    course_progress: Mapped[List["UserCourseProgress"]] = relationship(
        back_populates="capsule",
        cascade="all, delete-orphan",
    )
    
 

    def __repr__(self):
        return f"<💊Capsule(id={self.id}, title='{self.title}')>"