# Fichier: nanshe/backend/app/api/v2/endpoints/user_router.py (CORRIGÉ)

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.schemas import user_schema, personalization_schema
from typing import List # Assurez-vous que List est importé
from app.crud import user_crud
from app.core import security
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user_model import User
from app.core.config import settings # <-- 1. ON IMPORTE LA CONFIG

router = APIRouter()

@router.post("/", response_model=user_schema.User, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(user_in: user_schema.UserCreate, db: Session = Depends(get_db)):
    # (le reste de cette fonction ne change pas)
    if user_crud.get_user_by_email(db, email=user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if user_crud.get_user_by_username(db, username=user_in.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    user = user_crud.create_user(db=db, user=user_in)
    return user

@router.post("/login")
def login_for_access_token(
    response: Response,
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

    # 2. ON DÉFINIT LE PARAMÈTRE SECURE DYNAMIQUEMENT
    # Il sera True si settings.ENVIRONMENT == "production", sinon False.
    secure_cookie = settings.ENVIRONMENT == "production"

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite="lax",
        secure=secure_cookie, # <-- 3. ON UTILISE NOTRE VARIABLE
        path="/"
    )
    return {"message": "Login successful"}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Logout successful"}

@router.get("/me", response_model=user_schema.User)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/me/performance/{course_id}", response_model=List[personalization_schema.UserTopicPerformance])
def read_user_performance(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupère les statistiques de performance de l'utilisateur pour un cours donné."""
    performance_data = user_crud.get_user_performance_in_course(
        db=db, user_id=current_user.id, course_id=course_id
    )
    return performance_data