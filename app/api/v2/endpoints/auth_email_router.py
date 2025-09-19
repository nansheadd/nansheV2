from fastapi import APIRouter, Depends, Body
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user.user_model import User
from app.services.email.email_service import (
    send_confirm_email, send_reset_email, get_valid_token, mark_token_used
)
from app.models.email.email_token import EmailTokenPurpose
from app.core.security import get_password_hash

router = APIRouter()

# DB dependency (sync session)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class SendEmailIn(BaseModel):
    email: EmailStr
    lang: str = 'fr'

@router.post("/send-confirmation", status_code=202)
async def send_confirmation(data: SendEmailIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # 202 pour éviter la révélation d’existence de compte
        return {"sent": True}
    # Si déjà vérifié, on renvoie 202 aussi
    if getattr(user, 'is_email_verified', False) or getattr(user, 'email_verified_at', None) is not None:
        return {"sent": True}
    await send_confirm_email(db, user, data.lang)
    return {"sent": True}

class VerifyIn(BaseModel):
    token: str

@router.post("/verify-email")
def verify_email(data: VerifyIn, db: Session = Depends(get_db)):
    et = get_valid_token(db, data.token, EmailTokenPurpose.verify)
    user = et.user
    # Marquer comme vérifié (compat : bool ou datetime)
    if hasattr(user, 'is_email_verified'):
        user.is_email_verified = True
    if hasattr(user, 'email_verified_at'):
        from datetime import datetime
        user.email_verified_at = datetime.utcnow()
    db.add(user)
    mark_token_used(db, et)
    return {"verified": True}

@router.post("/forgot-password", status_code=202)
async def forgot_password(data: SendEmailIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        return {"sent": True}
    await send_reset_email(db, user, data.lang)
    return {"sent": True}

class ResetIn(BaseModel):
    token: str
    new_password: str

@router.post("/reset-password")
def reset_password(data: ResetIn, db: Session = Depends(get_db)):
    et = get_valid_token(db, data.token, EmailTokenPurpose.reset)
    user = et.user
    user.hashed_password = get_password_hash(data.new_password)
    db.add(user)
    mark_token_used(db, et)
    return {"reset": True}