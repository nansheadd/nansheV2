# Fichier: nanshe/backend/app/api/v2/dependencies.py (Version Complète)

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.db.session import SessionLocal
from app.core import security
from app.models.user_model import User
from app.crud import user_crud

# This tells FastAPI where to go to get a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v2/users/login")

def get_db():
    """
    Dépendance FastAPI pour obtenir une session de base de données.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """
    Dépendance pour obtenir l'utilisateur actuel à partir d'un token JWT.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.get(User, int(user_id)) # Utilise db.get pour une recherche par clé primaire plus propre

    if user is None:
        raise credentials_exception
    return user