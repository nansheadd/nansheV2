# Fichier: backend/app/api/v2/endpoints/toolbox_router.py (NOUVEAU)
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User
from app.crud import (
    coach_conversation_crud,
    coach_energy_crud,
    coach_tutorial_crud,
    toolbox_crud,
    toolbox_notes_crud,
)
from app.schemas.toolbox import (
    CoachConversationMessageOut,
    CoachConversationThreadDetail,
    CoachConversationThreadOut,
    CoachTutorialStateOut,
    CoachTutorialStateUpdate,
    MoleculeNoteCreate,
    MoleculeNoteOut,
    MoleculeNoteUpdate,
)
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, List, Literal

from app.models.toolbox.coach_conversation_model import (
    CoachConversationRole,
    CoachConversationThread,
)
from app.models.toolbox.molecule_note_model import MoleculeNote
from app.api.v2.endpoints.learning_router import _build_empty_journal_response

router = APIRouter()

class CoachRequest(BaseModel):
    message: str
    context: Dict[str, Any]
    history: List[Dict[str, str]]
    quick_action: str | None = None
    selection: Dict[str, Any] | None = None
    thread_id: int | None = Field(default=None, gt=0)


class CoachFeedbackPayload(BaseModel):
    feedback: Literal["like", "dislike", None] = Field(default=None)


class CoachMessageNotePayload(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    molecule_id: int | None = Field(default=None, gt=0)
    content: str | None = Field(default=None)


class JournalRequest(BaseModel):
    """Payload accepted by journal endpoints for future extensibility."""

    model_config = ConfigDict(extra="allow")

    limit: int | None = Field(default=None, ge=1, le=50)


def _extract_limit(limit: int | None, payload: JournalRequest | None) -> int:
    """Return the validated limit with fallback to the default."""

    if payload and payload.limit is not None:
        return payload.limit
    if limit is not None:
        return limit
    return 10

@router.get(
    "/coach/tutorials/states",
    response_model=list[CoachTutorialStateOut],
    summary="Lister les états de tutoriel pour l'utilisateur",
)
def list_coach_tutorial_states(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CoachTutorialStateOut]:
    states = coach_tutorial_crud.list_states_for_user(db, current_user)
    return [CoachTutorialStateOut.model_validate(state) for state in states]


@router.put(
    "/coach/tutorials/{tutorial_key}/state",
    response_model=CoachTutorialStateOut,
    summary="Mettre à jour l'état d'un tutoriel coach",
)
def update_coach_tutorial_state(
    tutorial_key: str,
    payload: CoachTutorialStateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachTutorialStateOut:
    if payload.status is None and payload.last_step_index is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no_update_payload",
        )

    state = coach_tutorial_crud.upsert_state(
        db,
        current_user,
        tutorial_key=tutorial_key,
        status=payload.status,
        last_step_index=payload.last_step_index,
    )
    return CoachTutorialStateOut.model_validate(state)


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
            thread_id=request.thread_id,
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


def _list_threads_with_stats(
    db: Session,
    current_user: User,
) -> tuple[list[CoachConversationThread], dict[int, tuple[int, datetime | None]]]:
    threads = coach_conversation_crud.list_threads_for_user(db, current_user)
    stats = coach_conversation_crud.fetch_thread_statistics(db, (thread.id for thread in threads))
    return threads, stats


def _serialize_thread(
    thread: CoachConversationThread,
    stats: dict[int, tuple[int, datetime | None]],
) -> CoachConversationThreadOut:
    message_count, last_message_at = stats.get(thread.id, (0, None))
    return CoachConversationThreadOut.from_thread(
        thread,
        message_count=message_count,
        last_message_at=last_message_at,
    )


def _serialize_thread_detail(
    thread: CoachConversationThread,
    stats: dict[int, tuple[int, datetime | None]],
    messages: list[CoachConversationMessageOut] | list,
) -> CoachConversationThreadDetail:
    base = _serialize_thread(thread, stats)
    return CoachConversationThreadDetail(
        **base.model_dump(),
        messages=messages,
    )


def _get_thread_or_404(
    db: Session,
    current_user: User,
    thread_id: int,
) -> CoachConversationThread:
    thread = coach_conversation_crud.get_thread_for_user(db, current_user, thread_id)
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation introuvable")
    return thread


@router.get("/coach/conversations", response_model=list[CoachConversationThreadOut])
def list_coach_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CoachConversationThreadOut]:
    threads, stats = _list_threads_with_stats(db, current_user)
    return [_serialize_thread(thread, stats) for thread in threads]


def _latest_thread(
    db: Session,
    current_user: User,
) -> CoachConversationThreadOut | None:
    threads, stats = _list_threads_with_stats(db, current_user)
    if not threads:
        return None
    return _serialize_thread(threads[0], stats)


@router.get(
    "/coach/conversations/current",
    response_model=CoachConversationThreadOut | None,
    summary="Alias of the latest coach conversation thread",
)
def get_current_coach_conversation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachConversationThreadOut | None:
    return _latest_thread(db, current_user)


@router.get(
    "/coach/conversations/latest",
    response_model=CoachConversationThreadOut | None,
    summary="Alias of the latest coach conversation thread",
)
def get_latest_coach_conversation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachConversationThreadOut | None:
    return _latest_thread(db, current_user)


@router.get(
    "/coach/conversation",
    response_model=list[CoachConversationThreadOut],
    summary="Legacy alias for list_coach_conversations",
)
def list_coach_conversation_alias(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CoachConversationThreadOut]:
    return list_coach_conversations(db=db, current_user=current_user)


@router.get(
    "/coach/conversations/{thread_id}",
    response_model=CoachConversationThreadDetail,
)
def get_coach_conversation_detail(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachConversationThreadDetail:
    thread = _get_thread_or_404(db, current_user, thread_id)
    stats = coach_conversation_crud.fetch_thread_statistics(db, [thread.id])
    messages = coach_conversation_crud.list_messages_for_thread(db, thread)
    return _serialize_thread_detail(thread, stats, messages)


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
    thread = _get_thread_or_404(db, current_user, thread_id)

    messages = coach_conversation_crud.list_messages_for_thread(db, thread, limit=limit)
    return messages


@router.post(
    "/coach/conversations/{thread_id}/reset",
    response_model=CoachConversationThreadDetail,
)
def reset_coach_conversation(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachConversationThreadDetail:
    thread = _get_thread_or_404(db, current_user, thread_id)
    coach_conversation_crud.clear_thread_messages(db, thread)
    stats = coach_conversation_crud.fetch_thread_statistics(db, [thread.id])
    return _serialize_thread_detail(thread, stats, [])


@router.delete(
    "/coach/conversations/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_coach_conversation(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    thread = _get_thread_or_404(db, current_user, thread_id)
    coach_conversation_crud.delete_thread(db, thread)


@router.post(
    "/coach/conversations/{thread_id}/messages/{message_id}/feedback",
    response_model=CoachConversationMessageOut,
)
def set_coach_message_feedback(
    thread_id: int,
    message_id: int,
    payload: CoachFeedbackPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachConversationMessageOut:
    thread = _get_thread_or_404(db, current_user, thread_id)
    message = coach_conversation_crud.get_message_for_thread(db, thread, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message introuvable")
    if message.role != CoachConversationRole.COACH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seuls les messages du coach peuvent recevoir un avis.")
    updated = coach_conversation_crud.set_message_feedback(db, message, payload.feedback)
    return updated


@router.delete(
    "/coach/conversations/{thread_id}/messages/{message_id}/feedback",
    response_model=CoachConversationMessageOut,
)
def clear_coach_message_feedback(
    thread_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CoachConversationMessageOut:
    thread = _get_thread_or_404(db, current_user, thread_id)
    message = coach_conversation_crud.get_message_for_thread(db, thread, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message introuvable")
    if message.role != CoachConversationRole.COACH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seuls les messages du coach peuvent recevoir un avis.")
    updated = coach_conversation_crud.set_message_feedback(db, message, None)
    return updated


@router.post(
    "/coach/conversations/{thread_id}/messages/{message_id}/notes",
    response_model=MoleculeNoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_note_from_coach_message(
    thread_id: int,
    message_id: int,
    payload: CoachMessageNotePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MoleculeNoteOut:
    thread = _get_thread_or_404(db, current_user, thread_id)
    message = coach_conversation_crud.get_message_for_thread(db, thread, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message introuvable")
    if message.role != CoachConversationRole.COACH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seuls les messages du coach peuvent être ajoutés aux notes.")

    target_molecule_id = payload.molecule_id or thread.molecule_id
    if not target_molecule_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucune molécule associée pour créer la note.")

    title = payload.title or message.content.split("\n", 1)[0][:120]
    content = payload.content or message.content

    try:
        note = toolbox_notes_crud.create_note(
            db,
            current_user,
            molecule_id=target_molecule_id,
            title=title,
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    coach_conversation_crud.attach_note_reference(db, message, note.id)
    return _serialize_note(note)


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


@router.get("/journal", summary="Journal de progression (toolbox)")
def get_toolbox_journal(
    limit: int | None = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),  # noqa: ARG001 - réservé pour un usage futur
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - garde d'authentification
) -> dict:
    """Placeholder endpoint so the frontend can fetch toolbox journal data."""

    return _build_empty_journal_response(_extract_limit(limit, None))


@router.post("/journal", summary="Journal de progression (toolbox)")
def post_toolbox_journal(
    payload: JournalRequest | None = Body(default=None),
    db: Session = Depends(get_db),  # noqa: ARG001 - réservé pour un usage futur
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - garde d'authentification
) -> dict:
    """POST variant returning the same placeholder payload as the GET route."""

    return _build_empty_journal_response(_extract_limit(None, payload))


@router.get("/journal/entries", summary="Entrées du journal (toolbox)")
def get_toolbox_journal_entries(
    limit: int | None = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),  # noqa: ARG001 - réservé pour un usage futur
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - garde d'authentification
) -> dict:
    """Alias with the same placeholder payload as :func:`get_toolbox_journal`."""

    return _build_empty_journal_response(_extract_limit(limit, None))


@router.post("/journal/entries", summary="Entrées du journal (toolbox)")
def post_toolbox_journal_entries(
    payload: JournalRequest | None = Body(default=None),
    db: Session = Depends(get_db),  # noqa: ARG001 - réservé pour un usage futur
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - garde d'authentification
) -> dict:
    """POST alias mirroring :func:`post_toolbox_journal`."""

    return _build_empty_journal_response(_extract_limit(None, payload))
