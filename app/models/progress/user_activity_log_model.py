from sqlalchemy import Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base_class import Base

class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    
    # On enregistre le début et la fin de l'activité
    start_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # On peut lier l'activité à un élément précis si besoin
    capsule_id: Mapped[int] = mapped_column(Integer, ForeignKey("capsules.id"), nullable=True)
    atom_id: Mapped[int] = mapped_column(Integer, ForeignKey("atoms.id"), nullable=True)