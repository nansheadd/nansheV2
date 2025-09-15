# Fichier: nanshe/backend/app/models/user_model.py (VERSION FINALE CORRIGÉE)

from sqlalchemy import Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime

# --- IMPORTS NETTOYÉS ---
if TYPE_CHECKING:
    # On supprime toutes les références à l'ancien système de progression
    from .notification_model import Notification
    from .badge_model import UserBadge
    from ..capsule.capsule_model import Capsule
    from app.models.progress.user_character_strength_model import UserCharacterStrength
    from app.models.progress.user_vocabulary_strenght_model import UserVocabularyStrength
    from ..progress.user_course_progress_model import UserCourseProgress

    from ..capsule.utility_models import UserCapsuleProgress, UserCapsuleEnrollment # <-- La seule source de vérité
    from ..capsule.language_roadmap_model import LanguageRoadmap
    # Les autres imports de l'ancien système de progression sont supprimés
    from ..progress.user_knowledge_strength_model import UserKnowledgeStrength
    from ..progress.user_answer_log_model import UserAnswerLog


class User(Base):
    """
    Modèle SQLAlchemy représentant un utilisateur.
    """
    __tablename__ = "users"

    # --- Champs (inchangés) ---
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
    xp_points: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    
    # --- RELATIONS CORRIGÉES ET COHÉRENTES ---
    
    character_strengths: Mapped[List["UserCharacterStrength"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    vocabulary_strengths: Mapped[List["UserVocabularyStrength"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # ⚠️ Très probablement nécessaire aussi (voir ci-dessous)
    enrollments: Mapped[List["UserCapsuleEnrollment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    roadmaps: Mapped[List["LanguageRoadmap"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    created_capsules: Mapped[List["Capsule"]] = relationship(
        back_populates="creator"
    )

    capsule_progress: Mapped[List["UserCapsuleProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    course_progress: Mapped[List["UserCourseProgress"]] = relationship(back_populates="user")


    # Les autres relations qui n'ont pas de lien avec "Course" peuvent rester
    knowledge_strength: Mapped[List["UserKnowledgeStrength"]] = relationship(back_populates="user")
    answer_logs: Mapped[List["UserAnswerLog"]] = relationship(back_populates="user")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    user_badges: Mapped[List["UserBadge"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    
    @property
    def badges(self):
        return [user_badge.badge for user_badge in self.user_badges]

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
