from typing import cast

from fastapi import APIRouter, Request, status

from app.schemas.legal import ReportContentIn, ReportContentOut, SupportedLang
from app.services.email.email_service import send_report_ack_email

router = APIRouter(prefix="/legal", tags=["Legal"])

SUPPORTED_LANGS: set[SupportedLang] = {"fr", "en", "nl"}

ACK_MESSAGES = {
    "fr": "Merci ! Nous accusons réception de ton signalement.",
    "en": "Thanks! We recorded your report.",
    "nl": "Bedankt! We hebben je melding ontvangen.",
}


def resolve_lang(payload_lang: SupportedLang | None, accept_language: str | None) -> SupportedLang:
    if payload_lang in SUPPORTED_LANGS:
        return payload_lang

    if accept_language:
        for entry in accept_language.split(','):
            code = entry.split(';')[0].strip().lower()
            if not code:
                continue
            short = code[:2]
            if short in SUPPORTED_LANGS:
                return cast(SupportedLang, short)
    return "fr"


@router.post(
    "/report",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReportContentOut,
)
async def submit_report(payload: ReportContentIn, request: Request) -> ReportContentOut:
    lang = resolve_lang(payload.lang, request.headers.get("Accept-Language"))

    report_payload = {
        "url": payload.url,
        "reason": payload.reason,
        "name": payload.name,
        "email": payload.email,
        "good_faith": payload.good_faith,
    }

    await send_report_ack_email(report_payload, lang)

    return ReportContentOut(message=ACK_MESSAGES.get(lang, ACK_MESSAGES["fr"]))
