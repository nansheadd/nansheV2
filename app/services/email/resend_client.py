import resend
from app.core.config import settings

resend.api_key = settings.RESEND_API_KEY

async def send_email(to: str, subject: str, html: str):
    # Resend Python est sync côté HTTP; on l’appelle simplement ici
    return resend.Emails.send({
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    })