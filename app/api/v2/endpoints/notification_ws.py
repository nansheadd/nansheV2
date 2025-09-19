# Fichier: nanshev3/backend/app/api/v2/endpoints/notification_ws.py (VERSION FINALE)
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
from jose import jwt, JWTError, ExpiredSignatureError

from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_db, _decode_user_from_token
from app.notifications.websocket_manager import notification_ws_manager
import logging

router = APIRouter()


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    # 1) prendre le cookie si présent, sinon fallback sur le query param
    token = websocket.cookies.get("access_token") or websocket.query_params.get("token")
    if not token:
        logging.warning("WS refusée : aucun token (ni cookie ni query).")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        current_user = _decode_user_from_token(token, db)
    except ExpiredSignatureError:
        logging.warning("WS refusée : token expiré.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except Exception:
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