"""Database models for storing coach IA conversations by context."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as EnumSQL, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CoachConversationLocation(str, enum.Enum):
    """Different contexts supported by the coach conversation threads."""

    DASHBOARD = "dashboard"
    CAPSULE = "capsule"
    MOLECULE = "molecule"


class CoachConversationRole(str, enum.Enum):
    """Role of a message author inside a conversation thread."""

    USER = "user"
    COACH = "coach"


class CoachConversationThread(Base):
    """Group messages for a user and a specific location (dashboard/capsule/molecule)."""

    __tablename__ = "coach_conversation_threads"
    __table_args__ = (
        UniqueConstraint("user_id", "location_key", name="uq_coach_conversation_location"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    location: Mapped[CoachConversationLocation] = mapped_column(
        EnumSQL(CoachConversationLocation, name="coach_conversation_location"), nullable=False
    )
    location_key: Mapped[str] = mapped_column(String(255), nullable=False)
    capsule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("capsules.id", ondelete="SET NULL"), nullable=True)
    molecule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("molecules.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="coach_conversation_threads")
    capsule = relationship("Capsule")
    molecule = relationship("Molecule")
    messages = relationship(
        "CoachConversationMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="CoachConversationMessage.created_at",
    )

    @staticmethod
    def build_location_key(
        *,
        location: CoachConversationLocation,
        capsule_id: int | None = None,
        molecule_id: int | None = None,
    ) -> str:
        if location == CoachConversationLocation.DASHBOARD:
            return "dashboard"
        if location == CoachConversationLocation.CAPSULE:
            if capsule_id is None:
                raise ValueError("capsule_id is required for capsule conversations")
            return f"capsule:{capsule_id}"
        if location == CoachConversationLocation.MOLECULE:
            if molecule_id is None:
                raise ValueError("molecule_id is required for molecule conversations")
            return f"molecule:{molecule_id}"
        raise ValueError(f"Unsupported conversation location: {location}")


class CoachConversationMessage(Base):
    """Persist individual messages exchanged between the user and the coach."""

    __tablename__ = "coach_conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coach_conversation_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[CoachConversationRole] = mapped_column(
        EnumSQL(CoachConversationRole, name="coach_conversation_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    thread = relationship("CoachConversationThread", back_populates="messages")
