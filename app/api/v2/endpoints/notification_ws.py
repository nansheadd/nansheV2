# Fichier: nanshev3/backend/app/api/v2/endpoints/notification_ws.py (VERSION FINALE)
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.api.v2.dependencies import get_db, _decode_user_from_token
from app.notifications.websocket_manager import notification_ws_manager
import logging

router = APIRouter()


@router.websocket("/ws")
async def notifications_ws(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    token: str = Query(...)  # On attend obligatoirement le token dans l'URL
):
    """
    Établit une connexion WebSocket qui s'authentifie via un token
    passé en paramètre d'URL.
    """
    try:
        # On valide le token et on récupère l'utilisateur.
        # Si le token est invalide, une exception sera levée.
        current_user = _decode_user_from_token(token, db)
    except Exception:
        # Si l'authentification échoue, on ferme la connexion proprement.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Si l'authentification réussit, on connecte l'utilisateur.
    await notification_ws_manager.connect(current_user.id, websocket)
    logging.info(f"✅ WebSocket connecté pour l'utilisateur {current_user.id}")

    try:
        # On maintient la connexion ouverte.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_ws_manager.disconnect(current_user.id, websocket)
        logging.info(f"🔌 WebSocket déconnecté pour l'utilisateur {current_user.id}")
