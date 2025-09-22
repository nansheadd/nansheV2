from sqlalchemy import Integer, String, Boolean, DateTime, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime
import enum

if TYPE_CHECKING:
    from .notification_model import Notification
    from .badge_model import UserBadge
    from ..capsule.capsule_model import Capsule
    from ..progress.user_course_progress_model import UserCourseProgress
    from ..capsule.utility_models import UserCapsuleProgress, UserCapsuleEnrollment
    from ..capsule.language_roadmap_model import LanguageRoadmap
    from ..progress.user_answer_log_model import UserAnswerLog
    from ..progress.user_activity_log_model import UserActivityLog
    from ..analytics.classification_feedback_model import ClassificationFeedback
    from ..toolbox.coach_energy_model import CoachEnergyWallet

# On définit l'énumération pour le statut d'abonnement
class SubscriptionStatus(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"
    CANCELED = "canceled"

class User(Base):
    __tablename__ = "users"

    # --- Champs existants ---
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
    

    active_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profile_border_color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # --- NOUVEAUX CHAMPS POUR STRIPE ---
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscriptionstatus", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=SubscriptionStatus.FREE,
        server_default=SubscriptionStatus.FREE.value
    )
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    
    # --- Relations (inchangées) ---
    enrollments: Mapped[List["UserCapsuleEnrollment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    roadmaps: Mapped[List["LanguageRoadmap"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    created_capsules: Mapped[List["Capsule"]] = relationship(back_populates="creator")
    capsule_progress: Mapped[List["UserCapsuleProgress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    course_progress: Mapped[List["UserCourseProgress"]] = relationship(back_populates="user")
    activity_logs: Mapped[List["UserActivityLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    answer_logs: Mapped[List["UserAnswerLog"]] = relationship(back_populates="user")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    user_badges: Mapped[List["UserBadge"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    classification_feedbacks: Mapped[List["ClassificationFeedback"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    coach_energy_wallet: Mapped["CoachEnergyWallet"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    
    @property
    def badges(self):
        return [user_badge.badge for user_badge in self.user_badges]

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
