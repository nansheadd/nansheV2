from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v2.dependencies import get_current_user, get_db
from app.schemas.language_tools import (
    CharacterSessionCreate,
    CharacterTrainerResponse,
    AvailableLanguageOut,
)
from app.services.language_tool_service import LanguageToolService
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
