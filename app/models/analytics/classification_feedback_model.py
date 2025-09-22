from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any

from app.db.base_class import Base


class ClassificationFeedback(Base):
    __tablename__ = "classification_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    predicted_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    predicted_skill: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    final_domain: Mapped[str] = mapped_column(String(100), nullable=False)
    final_area: Mapped[str] = mapped_column(String(100), nullable=False)
    final_skill: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    user: Mapped["User"] = relationship(back_populates="classification_feedbacks")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<ClassificationFeedback(id={self.id}, domain='{self.final_domain}', "
            f"area='{self.final_area}', is_correct={self.is_correct})>"
        )
