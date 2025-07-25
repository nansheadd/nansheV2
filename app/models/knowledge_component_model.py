# Fichier: nanshe/backend/app/models/knowledge_component_model.py (CORRIGÉ)
from sqlalchemy import Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .level_model import Level
    from .user_knowledge_strength_model import UserKnowledgeStrength
    from .user_answer_log_model import UserAnswerLog

class KnowledgeComponent(Base):
    __tablename__ = "knowledge_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    level_id: Mapped[int] = mapped_column(Integer, ForeignKey("levels.id"))
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bloom_level: Mapped[str] = mapped_column(String(50))

    # --- CORRECTION ICI ---
    level: Mapped["Level"] = relationship(
        "Level", 
        back_populates="knowledge_components"
    )
    # --- FIN DE LA CORRECTION ---

    user_strengths: Mapped[List["UserKnowledgeStrength"]] = relationship(back_populates="knowledge_component")
    user_answers: Mapped[List["UserAnswerLog"]] = relationship(back_populates="knowledge_component")

    def __repr__(self):
        return f"<KnowledgeComponent(id={self.id}, title='{self.title}')>"