# Fichier: backend/app/models/analytics/ai_token_log_model.py (NOUVEAU)
from sqlalchemy import Integer, String, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
from datetime import datetime

class AITokenLog(Base):
    __tablename__ = "ai_token_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    feature: Mapped[str] = mapped_column(String(100)) # Ex: 'coach', 'course_generation'
    model_name: Mapped[str] = mapped_column(String(100))
    
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int] = mapped_column(Integer)
    
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)