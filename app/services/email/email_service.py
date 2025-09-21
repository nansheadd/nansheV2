from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.config import settings
from app.models.user.user_model import User
from app.models.email.email_token import EmailToken, EmailTokenPurpose
#from .resend_client import send_email
from .provider import send_email

from .templates import render_confirm, render_reset, render_report_ack


# Helpers TTL
CONFIRM_TTL = timedelta(hours=settings.EMAIL_CONFIRM_TTL_H)
RESET_TTL = timedelta(minutes=settings.EMAIL_RESET_TTL_MIN)

def create_token(db: Session, user: User, purpose: EmailTokenPurpose) -> EmailToken:
    token = EmailToken.new_token()
    expires = datetime.now(timezone.utc) + (CONFIRM_TTL if purpose == EmailTokenPurpose.verify else RESET_TTL)
    et = EmailToken(user_id=user.id, purpose=purpose, token=token, expires_at=expires)
    db.add(et)
    db.commit()
    db.refresh(et)
    return et

def mark_token_used(db: Session, et: EmailToken):
    et.used_at = datetime.now(timezone.utc)
    db.add(et)
    db.commit()

async def send_confirm_email(db: Session, user: User, lang: str = 'fr'):
    # crée un nouveau token (invalidant implicitement les anciens côté usage applicatif : tu peux supprimer les anciens ici si tu veux)
    et = create_token(db, user, EmailTokenPurpose.verify)
    verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email?token={et.token}"
    subject, html = render_confirm(verify_url, lang)
    return await send_email(user.email, subject, html)

async def send_reset_email(db: Session, user: User, lang: str = 'fr'):
    et = create_token(db, user, EmailTokenPurpose.reset)
    reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={et.token}"
    subject, html = render_reset(reset_url, lang)
    return await send_email(user.email, subject, html)


async def send_report_ack_email(report_payload: dict, lang: str = 'fr'):
    subject, html = render_report_ack(report_payload, lang)
    recipient = report_payload.get('email')
    if not recipient:
        raise ValueError("Report payload missing reporter email")
    return await send_email(recipient, subject, html)

# Vérifications

def get_valid_token(db: Session, token: str, purpose: EmailTokenPurpose) -> EmailToken:
    et = db.query(EmailToken).filter(EmailToken.token == token, EmailToken.purpose == purpose).first()
    if not et:
        raise HTTPException(status_code=400, detail="Invalid token")
    if et.used_at is not None:
        raise HTTPException(status_code=400, detail="Token already used")
    if et.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
    return et
