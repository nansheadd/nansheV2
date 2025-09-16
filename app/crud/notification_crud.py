# Fichier: nanshev3/backend/app/crud/notification_crud.py

from sqlalchemy.orm import Session
from typing import List
from app.models.user import notification_model
from app.schemas.user import notification_schema

def create_notification(db: Session, notification: notification_schema.NotificationCreate) -> notification_model.Notification:
    """Crée une nouvelle notification pour un utilisateur."""
    db_notification = notification_model.Notification(
        user_id=notification.user_id,
        title=notification.title,
        message=notification.message,
        category=notification.category,
        link=notification.link
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification

def get_notifications_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[notification_model.Notification]:
    """Récupère toutes les notifications d'un utilisateur, les plus récentes en premier."""
    return db.query(notification_model.Notification)\
             .filter(notification_model.Notification.user_id == user_id)\
             .order_by(notification_model.Notification.created_at.desc())\
             .offset(skip)\
             .limit(limit)\
             .all()

def get_unread_notifications_count(db: Session, user_id: int) -> int:
    """Compte le nombre de notifications non lues."""
    return db.query(notification_model.Notification)\
             .filter(
                 notification_model.Notification.user_id == user_id,
                 notification_model.Notification.status == notification_model.NotificationStatus.UNREAD
             )\
             .count()

def mark_as_read(db: Session, notification_id: int, user_id: int) -> notification_model.Notification | None:
    """Marque une notification spécifique comme lue."""
    db_notification = db.query(notification_model.Notification)\
                        .filter(notification_model.Notification.id == notification_id, notification_model.Notification.user_id == user_id)\
                        .first()
    if db_notification:
        db_notification.status = notification_model.NotificationStatus.READ
        db.commit()
        db.refresh(db_notification)
    return db_notification

def mark_all_as_read(db: Session, user_id: int):
    """Marque toutes les notifications non lues d'un utilisateur comme lues."""
    db.query(notification_model.Notification)\
      .filter(
          notification_model.Notification.user_id == user_id,
          notification_model.Notification.status == notification_model.NotificationStatus.UNREAD
      )\
      .update({"status": notification_model.NotificationStatus.READ})
    db.commit()
    return {"status": "success"}
