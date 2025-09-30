"""Persistence model for tracking coach tutorial progress per user."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CoachTutorialState(Base):
    """Store the status of a specific tutorial for a given user."""

    __tablename__ = "coach_tutorial_states"
    __table_args__ = (
        UniqueConstraint("user_id", "tutorial_key", name="uq_coach_tutorial_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tutorial_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    last_step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="tutorial_states")

    def mark_started(self) -> None:
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

    def mark_completed(self) -> None:
        self.completed_at = datetime.now(timezone.utc)
