# Fichier: nanshe/backend/app/api/v2/endpoints/user_router.py (CORRIGÉ)

from app.schemas.user import user_schema
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List # Assurez-vous que List est importé
from app.crud import user_crud
from app.crud import badge_crud
from app.core import security
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.core.config import settings # <-- 1. ON IMPORTE LA CONFIG
from app.schemas.capsule.capsule_schema import CapsuleProgressRead
from app.gamification.badge_rules import compute_profile_completeness
from app.services.email.email_service import send_confirm_email  # <-- import

router = APIRouter()

@router.post("/", response_model=user_schema.User, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    user_in: user_schema.UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    if user_crud.get_user_by_email(db, email=user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if user_crud.get_user_by_username(db, username=user_in.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    user = user_crud.create_user(db=db, user=user_in)

    # 🔔 ENVOI DU MAIL DE CONFIRMATION
    # langue depuis le header envoyé par le front (fallback fr)
    lang = request.headers.get("x-app-lang", "fr")
    try:
        await send_confirm_email(db, user, lang)
    except Exception as e:
        # log doux, on n'échoue pas l’inscription si l’email part mal
        import logging; logging.getLogger(__name__).warning(f"send_confirm_email failed: {e}")

    try:
        badge_crud.award_badge(db, user.id, "initiation-inscription")
    except Exception:
        pass
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
    try:
        # Badge première connexion
        badge_crud.award_badge(db, user.id, "voyageur-premiere-connexion")
    except Exception:
        pass
    return {"message": "Login successful"}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Logout successful"}

@router.get("/me", response_model=user_schema.User)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=user_schema.User)
def update_me(
    payload: user_schema.UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Met à jour les informations du profil de l'utilisateur (actuellement: full_name).
    Déclenche le badge de profil complété si le profil atteint 100%."""
    # Pour rester safe: on ne met à jour que full_name pour l'instant
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip() or None
    db.commit()
    db.refresh(current_user)

    # Calcul de complétion du profil et attribution du badge si applicable
    try:
        # Nombre d'inscriptions actives
        from app.models.capsule.utility_models import UserCapsuleEnrollment
        enrolled_count = db.query(UserCapsuleEnrollment).filter_by(user_id=current_user.id).count()
        completeness = compute_profile_completeness(
            has_full_name=bool(current_user.full_name),
            enrolled_count=enrolled_count,
        )
        if completeness >= 100:
            badge_crud.award_badge(db, current_user.id, "initiation-profil-complet")
    except Exception:
        pass

    return current_user

@router.get("/me/capsule-progress", response_model=List[CapsuleProgressRead])
def read_user_capsule_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne la progression de l'utilisateur sur toutes ses capsules actives."""

    return user_crud.get_user_capsule_progresses(db=db, user_id=current_user.id)
