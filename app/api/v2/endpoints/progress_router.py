# Fichier: backend/app/api/v2/endpoints/progress_router.py (FINAL)
from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from app.schemas import progress_schema
from app.crud import progress_crud
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user_model import User
from pydantic import BaseModel
from typing import List, Dict

router = APIRouter()

# --- NOUVEAUX SCHÉMAS POUR LE CHAT ---
class ChatMessage(BaseModel):
    author: str
    message: str

class ContinueDiscussionRequest(BaseModel):
    history: List[ChatMessage]
    user_message: str
# ------------------------------------

@router.post("/answer", status_code=status.HTTP_200_OK)
def submit_answer(
    answer_in: progress_schema.AnswerCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Endpoint pour la PREMIÈRE soumission d'une réponse à un exercice."""
    result = progress_crud.process_user_answer(
        db=db, user=current_user, answer_in=answer_in, background_tasks=background_tasks
    )
    return result

@router.post("/discussion/{answer_log_id}/continue", response_model=Dict)
def continue_discussion(
    answer_log_id: int,
    request: ContinueDiscussionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Endpoint pour continuer une conversation avec l'IA."""
    updated_log = progress_crud.add_message_to_discussion(
        db=db, 
        answer_log_id=answer_log_id, 
        user=current_user,
        history=request.dict().get('history', []),
        user_message=request.user_message
    )
    if not updated_log:
        raise HTTPException(status_code=404, detail="Discussion non trouvée ou accès refusé.")
    
    # On renvoie le feedback complet qui contient le nouvel historique
    return updated_log.ai_feedback

@router.post("/reset/chapter/{chapter_id}", status_code=status.HTTP_200_OK)
def reset_chapter_answers(
    chapter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Réinitialise toutes les réponses d'un utilisateur pour un chapitre donné."""
    return progress_crud.reset_user_answers_for_chapter(db=db, user_id=current_user.id, chapter_id=chapter_id)