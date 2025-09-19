# app/services/email/provider.py
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def send_email(to: str, subject: str, html: str):
    provider = settings.MAIL_PROVIDER.lower()

    if provider == "sendgrid":
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        if not settings.SENDGRID_API_KEY:
            raise RuntimeError("SENDGRID_API_KEY manquant")

        message = Mail(
            from_email=settings.EMAIL_FROM,  # doit être la même adresse validée en Single Sender
            to_emails=to,                    # mets TON adresse perso le temps de tester
            subject=subject,
            html_content=html
        )

        # l’SDK est sync; on l’exécute dans un thread
        import anyio
        def _send():
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            return sg.send(message)

        resp = await anyio.to_thread.run_sync(_send)
        # Logs utiles
        msg_id = resp.headers.get('X-Message-Id') or resp.headers.get('X-Message-Id'.lower())
        logger.info(f"SendGrid → status={resp.status_code} message_id={msg_id}")
        # Affiche le body si status >= 400
        try:
            body = resp.body.decode() if hasattr(resp.body, 'decode') else str(resp.body)
        except Exception:
            body = str(resp.body)
        if resp.status_code >= 400:
            logger.error(f"SendGrid error body: {body}")
            raise RuntimeError(f"SendGrid error {resp.status_code}: {body}")
        return {"status": resp.status_code, "message_id": msg_id}
    
    else:
        print("SEND GRID ECHEC")
