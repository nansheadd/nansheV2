# Fichier: nanshe/backend/app/api/v2/endpoints/user_router.py (CORRIGÉ)

from fastapi import APIRouter, Depends, HTTPException, status
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

@router.post("/login", response_model=token_schema.Token) # La route est maintenant "/login"
def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_crud.get_user_by_username(db, username=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = security.create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=user_schema.User) # La route est maintenant "/me"
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user