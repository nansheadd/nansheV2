import logging
from fastapi import Depends, HTTPException, status, Request, WebSocket, Query
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import SessionLocal
from app.core import security
from app.models.user.user_model import User

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _decode_user_from_token(token: str | None, db: Session) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    if not token:
        log.warning("Validation échouée: Pas de token fourni.")
        raise credentials_exception

    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            log.warning("Validation échouée: Le token ne contient pas de 'sub'.")
            raise credentials_exception
        
        user_id = int(user_id_str)
    except (JWTError, ValueError, TypeError):
        log.warning("Validation échouée: Le token est invalide ou mal formé.")
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None:
        log.warning(f"Validation échouée: Utilisateur avec ID {user_id} non trouvé.")
        raise credentials_exception
    
    log.info(f"Utilisateur {user.id} validé avec succès via token.")
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    return _decode_user_from_token(token, db)