from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class FeaturePoll(Base):
    __tablename__ = "feature_polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    max_votes_free: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    max_votes_premium: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    options: Mapped[List["FeaturePollOption"]] = relationship(
        back_populates="poll",
        cascade="all, delete-orphan",
        order_by="FeaturePollOption.position",
    )
    votes: Mapped[List["FeaturePollVote"]] = relationship(
        back_populates="poll",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<FeaturePoll(id={self.id}, slug='{self.slug}')>"


class FeaturePollOption(Base):
    __tablename__ = "feature_poll_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poll_id: Mapped[int] = mapped_column(Integer, ForeignKey("feature_polls.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    poll: Mapped[FeaturePoll] = relationship(back_populates="options")
    votes: Mapped[List["FeaturePollVote"]] = relationship(
        back_populates="option",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<FeaturePollOption(id={self.id}, title='{self.title}')>"


class FeaturePollVote(Base):
    __tablename__ = "feature_poll_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "option_id", "user_id", name="uq_vote_user_option"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poll_id: Mapped[int] = mapped_column(Integer, ForeignKey("feature_polls.id"), index=True)
    option_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("feature_poll_options.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    votes: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    poll: Mapped[FeaturePoll] = relationship(back_populates="votes")
    option: Mapped[FeaturePollOption] = relationship(back_populates="votes")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            "<FeaturePollVote(id={0}, poll_id={1}, option_id={2}, user_id={3}, votes={4})>".format(
                self.id,
                self.poll_id,
                self.option_id,
                self.user_id,
                self.votes,
            )
        )
