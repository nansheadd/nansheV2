# Fichier: app/api/v2/dependencies.py (CORRIGÉ pour les Cookies)
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import SessionLocal
from app.core import security
from app.models.user.user_model import User

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Dépendance pour obtenir l'utilisateur actuel à partir du token
    stocké dans le cookie httponly.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    token = request.cookies.get("access_token") # On lit le cookie
    if token is None:
        raise credentials_exception
        
    try:
        # On enlève le "Bearer " s'il est présent
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        payload = jwt.decode(
            token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.get(User, int(user_id))
    
    if user is None:
        raise credentials_exception
    return user