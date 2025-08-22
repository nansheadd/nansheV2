# Fichier: backend/app/models/user_answer_log_model.py (FINAL CORRIGÉ)
from sqlalchemy import Integer, String, JSON, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..user.user_model import User
    from ..course.knowledge_graph_model import KnowledgeComponent

class UserAnswerLog(Base):
    __tablename__ = "user_answer_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    component_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_components.id"), nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_answer_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default='pending_review', nullable=False, index=True)
    ai_feedback: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=True)
    
    # --- Relations ---
    user: Mapped["User"] = relationship("User", back_populates="answer_logs")
    
    # On spécifie la clé étrangère pour aider SQLAlchemy à résoudre la dépendance
    knowledge_component: Mapped["KnowledgeComponent"] = relationship(
        "KnowledgeComponent", 
        back_populates="user_answers",
        foreign_keys=[component_id]
    )

    def __repr__(self):
        return f"<UserAnswerLog(id={self.id}, status='{self.status}')>"