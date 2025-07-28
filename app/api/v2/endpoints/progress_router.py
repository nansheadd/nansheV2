# Fichier: backend/app/api/v2/endpoints/progress_router.py (CORRIGÉ)
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.schemas import progress_schema
from app.crud import progress_crud
# --- CORRECTION ICI ---
# On importe get_db depuis notre fichier de dépendances centralisé
from app.api.v2.dependencies import get_db, get_current_user
# --- FIN DE LA CORRECTION ---
from app.models.user_model import User

router = APIRouter()

# On a supprimé la fonction get_db() qui était dupliquée ici.

@router.post("/answer", response_model=progress_schema.AnswerResult, status_code=status.HTTP_200_OK)
def submit_answer(
    answer_in: progress_schema.AnswerCreate,
    db: Session = Depends(get_db), # Utilise maintenant le bon get_db
    current_user: User = Depends(get_current_user)
):
    """
    Permet à un utilisateur de soumettre une réponse à un exercice.
    """
    result = progress_crud.process_user_answer(db=db, user=current_user, answer_in=answer_in)
    return result