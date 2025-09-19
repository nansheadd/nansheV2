from datetime import datetime, timedelta
import secrets
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum

class EmailTokenPurpose(str, enum.Enum):
    verify = "verify"
    reset = "reset"

class EmailToken(Base):
    __tablename__ = "email_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    purpose = Column(Enum(EmailTokenPurpose), nullable=False)
    token = Column(String(200), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    user = relationship("User")

    @staticmethod
    def new_token(length: int = 48) -> str:
        return secrets.token_urlsafe(length)

Index("ix_email_tokens_token_purpose", EmailToken.token, EmailToken.purpose)