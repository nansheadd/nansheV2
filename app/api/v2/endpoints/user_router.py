# Fichier: nanshe/backend/app/api/v2/endpoints/user_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.schemas import user_schema, token_schema
from app.crud import user_crud
from app.core import security
from app.api.v2.dependencies import get_db

router = APIRouter()

@router.post("/users", response_model=user_schema.User, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(user_in: user_schema.UserCreate, db: Session = Depends(get_db)):
    """
    Endpoint pour créer un nouvel utilisateur.
    """
    # Vérifie si l'email ou le username n'est pas déjà pris
    if user_crud.get_user_by_email(db, email=user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if user_crud.get_user_by_username(db, username=user_in.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    user = user_crud.create_user(db=db, user=user_in)
    return user

@router.post("/login/access-token", response_model=token_schema.Token)
def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint pour se connecter et obtenir un token JWT.
    """
    user = user_crud.get_user_by_username(db, username=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = security.create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}