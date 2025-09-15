# Fichier: nanshev3/backend/app/api/v2/endpoints/notification_router.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.crud import notification_crud
from app.schemas.user import notification_schema

router = APIRouter()

@router.get("/", response_model=List[notification_schema.NotificationRead], summary="Lister les notifications de l'utilisateur")
def read_notifications(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupère les notifications pour l'utilisateur actuellement connecté."""
    return notification_crud.get_notifications_by_user(db, user_id=current_user.id, skip=skip, limit=limit)

@router.get("/unread-count", response_model=dict, summary="Compter les notifications non lues")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retourne le nombre de notifications non lues."""
    count = notification_crud.get_unread_notifications_count(db, user_id=current_user.id)
    return {"unread_count": count}

@router.post("/{notification_id}/read", response_model=notification_schema.NotificationRead, summary="Marquer une notification comme lue")
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change le statut d'une notification de 'unread' à 'read'."""
    return notification_crud.mark_as_read(db, notification_id=notification_id, user_id=current_user.id)

@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT, summary="Marquer toutes les notifications comme lues")
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marque en une seule fois toutes les notifications de l'utilisateur comme lues."""
    notification_crud.mark_all_as_read(db, user_id=current_user.id)
    return