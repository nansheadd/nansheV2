# Fichier: nanshev3/backend/app/schemas/user/notification_schema.py

from pydantic import BaseModel
from datetime import datetime
from app.models.user.notification_model import NotificationCategory, NotificationStatus

# Schéma de base
class NotificationBase(BaseModel):
    title: str
    message: str
    category: NotificationCategory
    link: str | None = None

# Schéma pour la création (utilisé en interne)
class NotificationCreate(NotificationBase):
    user_id: int

# Schéma pour la lecture (envoyé au client)
class NotificationRead(NotificationBase):
    id: int
    status: NotificationStatus
    created_at: datetime

    class Config:
        from_attributes = True