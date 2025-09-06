# Gemini/backend/app/models/user/badge_model.py

from __future__ import annotations
from sqlalchemy import Integer, String, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .user_model import User

class Badge(Base):
    __tablename__ = "badges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # ... (autres colonnes de Badge)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    description: Mapped[str] = mapped_column(String)
    icon: Mapped[Optional[str]] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, index=True, default="Général")
    points: Mapped[int] = mapped_column(Integer, default=10)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)

    user_badges: Mapped[List["UserBadge"]] = relationship(back_populates="badge")

class UserBadge(Base):
    __tablename__ = "user_badges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    badge_id: Mapped[int] = mapped_column(ForeignKey("badges.id"))
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="user_badges")
    badge: Mapped["Badge"] = relationship(back_populates="user_badges")