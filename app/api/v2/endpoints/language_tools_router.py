from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v2.dependencies import get_current_user, get_db
from app.schemas.language_tools import (
    AvailableLanguageOut,
    CharacterSessionCreate,
    CharacterTrainerResponse,
    DialoguePracticeRequest,
    DialoguePracticeResponse,
    VocabularySessionCreate,
    VocabularyTrainerResponse,
)
from app.services.language_tool_service import LanguageToolService
from app.services.dialogue_practice_service import DialoguePracticeService
from app.services.vocabulary_tool_service import VocabularyToolService
from app.models.user.user_model import User
from sqlalchemy.orm import Session

router = APIRouter()


@router.get(
    "/languages",
    response_model=List[AvailableLanguageOut],
    summary="Lister les langues ayant un module d'alphabet pour l'utilisateur",
)
def list_available_languages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AvailableLanguageOut]:
    service = LanguageToolService(db=db, user=current_user)
    languages = service.list_available_languages()
    return [AvailableLanguageOut.model_validate(entry) for entry in languages]


@router.get(
    "/character-trainer/{language}",
    response_model=CharacterTrainerResponse,
    summary="Récupérer les jeux de caractères d'une langue et le statut d'apprentissage",
)
def get_character_trainer(
    language: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CharacterTrainerResponse:
    service = LanguageToolService(db=db, user=current_user)
    data = service.get_character_trainer(language)
    return CharacterTrainerResponse.model_validate(data)


@router.post(
    "/character-trainer/{language}/session",
    response_model=CharacterTrainerResponse,
    status_code=status.HTTP_200_OK,
    summary="Enregistrer une session d'entraînement et renvoyer l'état mis à jour",
)
def post_character_session(
    language: str,
    payload: CharacterSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CharacterTrainerResponse:
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_items")
    service = LanguageToolService(db=db, user=current_user)
    service.record_character_session(language, (item.model_dump() for item in payload.items))
    data = service.get_character_trainer(language)
    return CharacterTrainerResponse.model_validate(data)


@router.get(
    "/vocabulary-trainer/{language}",
    response_model=VocabularyTrainerResponse,
    summary="Récupérer la liste de vocabulaire étudiée pour une langue donnée",
)
def get_vocabulary_trainer(
    language: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VocabularyTrainerResponse:
    service = VocabularyToolService(db=db, user=current_user)
    data = service.get_vocabulary_trainer(language)
    return VocabularyTrainerResponse.model_validate(data)


@router.post(
    "/vocabulary-trainer/{language}/session",
    response_model=VocabularyTrainerResponse,
    status_code=status.HTTP_200_OK,
    summary="Enregistrer une session d'entraînement vocabulaire et renvoyer l'état mis à jour",
)
def post_vocabulary_session(
    language: str,
    payload: VocabularySessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VocabularyTrainerResponse:
    if not payload.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_items")
    service = VocabularyToolService(db=db, user=current_user)
    service.record_vocabulary_session(language, (item.model_dump() for item in payload.items))
    data = service.get_vocabulary_trainer(language)
    return VocabularyTrainerResponse.model_validate(data)


@router.post(
    "/dialogue-practice/respond",
    response_model=DialoguePracticeResponse,
    summary="Obtenir une réponse IA pour un dialogue d'entraînement",
)
def post_dialogue_practice(
    payload: DialoguePracticeRequest,
    current_user: User = Depends(get_current_user),
) -> DialoguePracticeResponse:
    if not payload.user_message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_message")

    service = DialoguePracticeService(user=current_user)
    response = service.respond(
        language_name=payload.language,
        language_code=payload.language_code,
        scenario=payload.scenario,
        history=[turn.model_dump() for turn in payload.history],
        user_message=payload.user_message,
        cefr=payload.cefr,
        focus_vocabulary=[word.model_dump() for word in payload.focus_vocabulary],
    )
    return DialoguePracticeResponse.model_validate(response)
