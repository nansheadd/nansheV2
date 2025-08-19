# app/models/analytics/feedback_model.py
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from app.db.base_class import Base
from app.models.user.user_model import User
import enum

class FeedbackRating(enum.Enum):
    liked = "liked"
    disliked = "disliked"

class FeedbackStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"

class ContentFeedback(Base):
    __tablename__ = "content_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_type: Mapped[str] = mapped_column(String(50), index=True)
    content_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user: Mapped["User"] = relationship()

    # 👉 On stocke des strings, pas des Enum Python
    rating: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)

    # Coercition : si jamais on te passe un Enum, on le convertit en .value
    @validates("rating", "status")
    def _coerce_enum_to_str(self, key, value):
        if isinstance(value, enum.Enum):
            return value.value
        return value

    # (optionnel) Accès confort en Enum côté Python
    @property
    def rating_enum(self) -> FeedbackRating:
        return FeedbackRating(self.rating)

    @property
    def status_enum(self) -> FeedbackStatus:
        return FeedbackStatus(self.status)

    def __repr__(self):
        return f"<Feedback(id={self.id}, content='{self.content_type}:{self.content_id}', rating='{self.rating}')>"
