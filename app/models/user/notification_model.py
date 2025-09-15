# Fichier: nanshev3/backend/app/models/user/notification_model.py

import enum
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Enum
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.user.user_model import User

class NotificationCategory(enum.Enum):
    BADGE = "badge"
    CAPSULE = "capsule"
    MENTOR = "mentor"
    GENERAL = "general"

class NotificationStatus(enum.Enum):
    UNREAD = "unread"
    READ = "read"

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    category = Column(Enum(NotificationCategory), nullable=False, default=NotificationCategory.GENERAL)
    status = Column(Enum(NotificationStatus), nullable=False, default=NotificationStatus.UNREAD)
    
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    
    # Un lien cliquable pour rediriger l'utilisateur (ex: /badges/nouveau-badge)
    link = Column(String, nullable=True) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notifications")

# N'oubliez pas d'ajouter cette relation dans votre modèle User (user_model.py)
# à l'intérieur de la classe User:
# notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")