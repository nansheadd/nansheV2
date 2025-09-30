"""Service d'entraînement pour les dialogues assistés par IA."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core import ai_service

logger = logging.getLogger(__name__)


class DialoguePracticeService:
    def __init__(self, *, user) -> None:
        self.user = user

    def respond(
        self,
        *,
        language_name: str,
        language_code: str | None,
        scenario: str,
        history: List[Dict[str, str]],
        user_message: str,
        cefr: str | None,
        focus_vocabulary: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """Obtient une réplique de l'IA pour le dialogue en cours."""
        try:
            payload = ai_service.respond_language_dialogue(
                language_name=language_name,
                lang_code=language_code,
                scenario=scenario,
                history=history,
                user_message=user_message,
                cefr=cefr,
                focus_vocabulary=focus_vocabulary,
            )
        except Exception as exc:
            logger.error("DialoguePracticeService: erreur lors de l'appel IA: %s", exc, exc_info=True)
            payload = {
                "reply_tl": "Je n'ai pas bien compris, pourrais-tu répéter s'il te plaît ?",
                "reply_transliteration": "",
                "reply_translation_fr": "Je n'ai pas bien compris, peux-tu répéter ?",
                "feedback_fr": "La connexion à l'assistant est instable, reformule ta phrase pour continuer.",
                "suggested_keywords": [],
            }
        return payload
