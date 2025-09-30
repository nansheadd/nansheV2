# Fichier: nanshe/backend/app/api/v2/endpoints/user_router.py (CORRIGÉ)

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.schemas.user import user_schema
from app.crud import user_crud
from app.crud import badge_crud
from app.core import security
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User, SubscriptionStatus
from app.core.config import settings
from app.schemas.capsule.capsule_schema import CapsuleProgressRead
from app.gamification.badge_rules import compute_profile_completeness
from app.services.email.email_service import send_confirm_email

router = APIRouter()
logger = logging.getLogger(__name__)

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
        logger.warning("send_confirm_email failed: %s", e)

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
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="inactive_user")
    if user.account_deletion_requested_at is not None:
        raise HTTPException(status_code=403, detail="account_deletion_scheduled")

    # ⚠️ IMPORTANT: create_access_token doit insérer {"sub": "<user_id_str>"}
    access_token = security.create_access_token(subject=str(user.id))

    # Cookie cross-site pour front/back sur domaines différents (Vercel)
    secure_cookie = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,   # JWT brut (pas "Bearer ")
        httponly=True,
        samesite="none",      # <- crucial pour cross-site
        secure=secure_cookie, # <- True en prod
        path="/",
    )

    # Tu renvoies aussi le token dans le body pour le fallback localStorage (dev)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"message": "Logout successful"})
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="none",
        secure=settings.ENVIRONMENT == "production",
    )
    return response

@router.get("/me", response_model=user_schema.User)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=user_schema.User)
async def update_me(
    payload: user_schema.UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Met à jour les informations du profil de l'utilisateur.

    Les champs gérés: ``full_name``, ``username`` et ``email``. Lorsque l'adresse e-mail change,
    une nouvelle confirmation est envoyée et le badge de profil complété est recalculé."""

    has_changes = False
    email_changed = False

    if payload.full_name is not None:
        new_full_name = payload.full_name.strip() or None
        if new_full_name != current_user.full_name:
            current_user.full_name = new_full_name
            has_changes = True

    if payload.active_title is not None:
        new_active_title = payload.active_title.strip() or None
        if new_active_title != current_user.active_title:
            current_user.active_title = new_active_title
            has_changes = True

    if payload.profile_border_color is not None:
        new_border_color = payload.profile_border_color.strip() or None
        if new_border_color != current_user.profile_border_color:
            current_user.profile_border_color = new_border_color
            has_changes = True

    if payload.username is not None:
        new_username = payload.username.strip()
        if not new_username:
            raise HTTPException(status_code=400, detail="username_empty")
        if new_username != current_user.username:
            if user_crud.get_user_by_username(db, username=new_username):
                raise HTTPException(status_code=400, detail="Username already taken")
            current_user.username = new_username
            has_changes = True

    if payload.email is not None:
        new_email = payload.email.strip()
        if new_email != current_user.email:
            if user_crud.get_user_by_email(db, email=new_email):
                raise HTTPException(status_code=400, detail="Email already registered")
            current_user.email = new_email
            current_user.is_email_verified = False
            email_changed = True
            has_changes = True

    if has_changes:
        db.commit()
        db.refresh(current_user)

    if email_changed:
        lang = request.headers.get("x-app-lang", "fr")
        try:
            await send_confirm_email(db, current_user, lang)
        except Exception as exc:
            logger.warning("send_confirm_email failed: %s", exc)

    if has_changes:
        try:
            from app.models.capsule.utility_models import UserCapsuleEnrollment

            enrolled_count = db.query(UserCapsuleEnrollment).filter_by(user_id=current_user.id).count()
            completeness = compute_profile_completeness(
                has_full_name=bool(current_user.full_name),
                enrolled_count=enrolled_count,
            )
            if completeness >= 100:
                badge_crud.award_badge(db, current_user.id, "initiation-profil-complet")
        except Exception as exc:
            logger.debug("Profile completeness check failed: %s", exc)

    return current_user


@router.delete("/me")
async def schedule_account_deletion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Planifie la suppression du compte de l'utilisateur dans 30 jours.

    Le compte est immédiatement désactivé. Les abonnements premium actifs sont révoqués et
    l'information de planification est renvoyée au client."""

    now = datetime.now(timezone.utc)
    scheduled_at = now + timedelta(days=30)
    canceled_subscriptions: list[str] = []

    if current_user.stripe_customer_id:
        try:
            from app.api.v2.endpoints.stripe_router import _cancel_active_subscriptions_for_customer

            canceled_subscriptions = _cancel_active_subscriptions_for_customer(
                current_user.stripe_customer_id
            )
        except Exception as exc:  # pragma: no cover - sécurité supplémentaire
            logger.warning(
                "Stripe cancellation failed for user %s: %s", current_user.id, exc
            )

    current_user.is_active = False
    current_user.subscription_status = SubscriptionStatus.CANCELED
    current_user.active_title = None
    current_user.profile_border_color = None
    current_user.account_deletion_requested_at = now
    current_user.account_deletion_scheduled_at = scheduled_at

    db.commit()
    db.refresh(current_user)

    return {
        "status": "scheduled",
        "requested_at": current_user.account_deletion_requested_at,
        "scheduled_at": current_user.account_deletion_scheduled_at,
        "canceled_stripe_subscriptions": canceled_subscriptions,
    }

@router.get("/me/capsule-progress", response_model=List[CapsuleProgressRead])
def read_user_capsule_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne la progression de l'utilisateur sur toutes ses capsules actives."""

    return user_crud.get_user_capsule_progresses(db=db, user_id=current_user.id)
