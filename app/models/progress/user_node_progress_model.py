# Fichier: backend/app/models/progress/user_node_progress_model.py

from sqlalchemy import Integer, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
import datetime

class UserNodeProgress(Base):
    __tablename__ = "user_node_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"), nullable=False)
    
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime.datetime] = mapped_column(nullable=True)

    # Contrainte pour s'assurer qu'un utilisateur n'a qu'une seule entrée par nœud
    __table_args__ = (UniqueConstraint('user_id', 'node_id', name='_user_node_uc'),)