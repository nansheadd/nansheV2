# Fichier: backend/app/api/v2/endpoints/toolbox_router.py (NOUVEAU)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.crud import (
    coach_conversation_crud,
    coach_energy_crud,
    toolbox_crud,
    toolbox_notes_crud,
)
from app.schemas.toolbox import (
    CoachConversationMessageOut,
    CoachConversationThreadOut,
    MoleculeNoteCreate,
    MoleculeNoteOut,
    MoleculeNoteUpdate,
)
from pydantic import BaseModel
from typing import List, Dict, Any

from app.models.toolbox.molecule_note_model import MoleculeNote

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
    try:
        return toolbox_crud.ask_coach(
            db=db,
            user=current_user,
            message=request.message,
            context=request.context,
            history=request.history,
            quick_action=request.quick_action,
            selection=request.selection,
        )
    except coach_energy_crud.CoachEnergyDepleted as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "coach_energy_depleted", "energy": exc.status},
        ) from exc


@router.get("/coach/energy")
def get_coach_energy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return coach_energy_crud.get_energy_status(db, current_user)


@router.get("/coach/conversations", response_model=list[CoachConversationThreadOut])
def list_coach_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CoachConversationThreadOut]:
    threads = coach_conversation_crud.list_threads_for_user(db, current_user)
    stats = coach_conversation_crud.fetch_thread_statistics(db, (thread.id for thread in threads))

    result: list[CoachConversationThreadOut] = []
    for thread in threads:
        message_count, last_message_at = stats.get(thread.id, (0, None))
        result.append(
            CoachConversationThreadOut.from_thread(
                thread,
                message_count=message_count,
                last_message_at=last_message_at,
            )
        )
    return result


@router.get(
    "/coach/conversations/{thread_id}/messages",
    response_model=list[CoachConversationMessageOut],
)
def list_coach_conversation_messages(
    thread_id: int,
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CoachConversationMessageOut]:
    thread = coach_conversation_crud.get_thread_for_user(db, current_user, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable")

    messages = coach_conversation_crud.list_messages_for_thread(db, thread, limit=limit)
    return messages


def _serialize_note(note: MoleculeNote) -> MoleculeNoteOut:
    molecule = getattr(note, "molecule", None)
    granule = getattr(molecule, "granule", None) if molecule else None
    capsule = getattr(granule, "capsule", None) if granule else None

    return MoleculeNoteOut(
        id=note.id,
        title=note.title,
        content=note.content,
        molecule_id=note.molecule_id,
        molecule_title=getattr(molecule, "title", None),
        capsule_id=getattr(capsule, "id", None),
        capsule_title=getattr(capsule, "title", None),
        capsule_domain=getattr(capsule, "domain", None),
        capsule_area=getattr(capsule, "area", None),
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


@router.get("/notes", response_model=list[MoleculeNoteOut])
def list_notes(
    molecule_id: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notes = toolbox_notes_crud.list_notes(db, current_user, molecule_id=molecule_id)
    return [_serialize_note(note) for note in notes]


@router.post("/notes", response_model=MoleculeNoteOut, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: MoleculeNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        note = toolbox_notes_crud.create_note(
            db,
            current_user,
            molecule_id=payload.molecule_id,
            title=payload.title,
            content=payload.content,
        )
    except ValueError as exc:  # Molecule not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _serialize_note(note)


@router.put("/notes/{note_id}", response_model=MoleculeNoteOut)
def update_note(
    note_id: int,
    payload: MoleculeNoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = toolbox_notes_crud.get_note_for_user(db, current_user, note_id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note introuvable")

    updated_note = toolbox_notes_crud.update_note(
        db,
        note,
        title=payload.title,
        content=payload.content,
    )
    return _serialize_note(updated_note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = toolbox_notes_crud.get_note_for_user(db, current_user, note_id)
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note introuvable")

    toolbox_notes_crud.delete_note(db, note)
