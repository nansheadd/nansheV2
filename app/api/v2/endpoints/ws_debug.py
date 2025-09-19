from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_db, get_current_user
from app.notifications.websocket_manager import notification_ws_manager

router = APIRouter()

class EmitBadgeBody(BaseModel):
    # Personnalisable mais avec des valeurs par défaut
    name: str = "Explorateur"
    description: str = "Tu as franchi une étape clé !"
    icon: str = "trophy"
    reward_xp: int = 25
    title: str | None = "Nouveau haut fait"
    type: str = "badge_awarded"  # pour rester aligné avec ton front

@router.post("/emit-badge", status_code=status.HTTP_204_NO_CONTENT)
async def emit_badge_test(
    body: EmitBadgeBody = EmitBadgeBody(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Push d'un badge de test au user courant (auth cookie).
    """
    payload = {
        "type": body.type,
        "badge": {
            "name": body.name,
            "description": body.description,
            "icon": body.icon,
        },
        "awarded_at": datetime.now(tz=timezone.utc).isoformat(),
        "reward_xp": body.reward_xp,
        "title": body.title,
    }

    # Envoi non bloquant via ton manager (garde la même API que chez toi)
    notification_ws_manager.notify(current_user.id, payload)
    return


@router.get("/state")
async def ws_state(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    count = len(notification_ws_manager.connections.get(current_user.id, set()))
    total_users = len(notification_ws_manager.connections)
    return {"user_id": current_user.id, "connections_for_user": count, "users_with_connections": total_users}