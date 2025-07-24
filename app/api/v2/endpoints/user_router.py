# Fichier: nanshe/backend/app/api/v2/endpoints/user_router.py (CORRIGÉ)

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.schemas import user_schema, token_schema
from app.crud import user_crud
from app.core import security
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user_model import User

router = APIRouter()

@router.post("/", response_model=user_schema.User, status_code=status.HTTP_201_CREATED) # La route est maintenant "/"
def create_user_endpoint(user_in: user_schema.UserCreate, db: Session = Depends(get_db)):
    if user_crud.get_user_by_email(db, email=user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if user_crud.get_user_by_username(db, username=user_in.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    user = user_crud.create_user(db=db, user=user_in)
    return user

@router.post("/login") # On retire le response_model, car on ne renvoie plus de token
def login_for_access_token(
    response: Response, # On injecte l'objet Response de FastAPI
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = user_crud.get_user_by_username(db, username=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    access_token = security.create_access_token(subject=user.id)
    
    # On attache le token à un cookie HttpOnly
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,       # Le cookie est inaccessible en JavaScript
        samesite="lax",      # Protection CSRF
        secure=False,        # Mettre à True en production (HTTPS)
        path="/"
    )
    return {"message": "Login successful"}

@router.post("/logout")
def logout(response: Response):
    """Déconnecte l'utilisateur en supprimant le cookie."""
    response.delete_cookie(key="access_token")
    return {"message": "Logout successful"}


@router.get("/me", response_model=user_schema.User) # La route est maintenant "/me"
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user