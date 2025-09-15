# Fichier: backend/app/models/progress/user_answer_log_model.py (CORRIGÉ)

from sqlalchemy import Integer, String, Boolean, JSON, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..user.user_model import User
    from ..capsule.atom_model import Atom # <-- On importe Atom

class UserAnswerLog(Base):
    """
    Modèle qui enregistre chaque réponse de l'utilisateur à un exercice (Atome).
    """
    __tablename__ = "user_answer_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    
    # --- CORRECTION : On lie l'enregistrement de réponse à un Atome ---
    atom_id: Mapped[int] = mapped_column(Integer, ForeignKey("atoms.id"), index=True)

    # --- Données sur la réponse ---
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_answer_json: Mapped[Dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- Relations ---
    user: Mapped["User"] = relationship(back_populates="answer_logs")
    atom: Mapped["Atom"] = relationship()