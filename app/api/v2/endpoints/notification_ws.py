# Fichier: nanshev3/backend/app/api/v2/endpoints/notification_ws.py (VERSION FINALE)
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_current_user_from_websocket, get_db
from app.notifications.websocket_manager import notification_ws_manager
import logging

router = APIRouter()


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    # 1) prendre le cookie si présent, sinon fallback sur le query param
    try:
        current_user = get_current_user_from_websocket(websocket, db)
    except HTTPException as exc:
        if exc.detail == "token_expired":
            logging.warning("WS refusée : token expiré.")
        else:
            logging.warning("WS refusée : token invalide (%s).", exc.detail)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await notification_ws_manager.connect(current_user.id, websocket)
    logging.info(f"✅ WebSocket connecté pour l'utilisateur {current_user.id}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_ws_manager.disconnect(current_user.id, websocket)
        logging.info(f"🔌 WebSocket déconnecté pour l'utilisateur {current_user.id}")
