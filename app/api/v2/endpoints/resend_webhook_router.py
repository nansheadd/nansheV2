from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.email.email_event import EmailEvent

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/webhooks/resend")
async def resend_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    # Resend envoie différents types d’événements : 'email.sent', 'email.delivered', 'email.bounced', etc.
    evt_type = payload.get('type')
    data = payload.get('data', {})
    message_id = data.get('id') or data.get('email_id')
    to = (data.get('to') or [''])[0] if isinstance(data.get('to'), list) else data.get('to')
    subject = data.get('subject')
    status = data.get('status') or data.get('delivery', {}).get('state')

    db_evt = EmailEvent(
        message_id=message_id,
        to=to,
        subject=subject,
        status=status,
        event_type=evt_type,
        payload=payload
    )
    db.add(db_evt)
    db.commit()
    return {"ok": True}