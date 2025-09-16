# Fichier: backend/app/api/v2/endpoints/toolbox_router.py (NOUVEAU)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.crud import toolbox_crud
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter()

class CoachRequest(BaseModel):
    message: str
    context: Dict[str, Any]
    history: List[Dict[str, str]]
    quick_action: str | None = None
    selection: Dict[str, Any] | None = None

@router.post("/coach")
def handle_coach_request(
    request: CoachRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    response = toolbox_crud.ask_coach(
        db=db, 
        user=current_user, 
        message=request.message, 
        context=request.context,
        history=request.history,
        quick_action=request.quick_action,
        selection=request.selection,
    )
    return {"response": response}
