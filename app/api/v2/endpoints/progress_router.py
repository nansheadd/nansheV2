"""Endpoints de progression alignés sur l'architecture Capsule."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v2.dependencies import get_db, get_current_user
from app.models.capsule.atom_model import Atom
from datetime import datetime

from app.models.capsule.utility_models import UserCapsuleProgress
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.schemas.progress.progress_schema import (
    ActivityEndRequest,
    ActivityStartRequest,
    AnswerLogCreate,
    CapsuleProgressResponse,
    UserStatsResponse,
)
from app.services.progress_service import ProgressService
from app.models.user.user_model import User
from app.models.progress.user_atomic_progress import UserAtomProgress
from app.services.services.capsule_service import CapsuleService
from app.services.srs_service import SRSService

router = APIRouter()


@router.post("/activity/start", response_model=dict, summary="Démarrer le suivi d'une activité")
def start_user_activity(
    payload: ActivityStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Crée une entrée de suivi temps passé pour une capsule/atome."""
    service = ProgressService(db=db, user_id=current_user.id)
    log_id = service.start_activity(payload.capsule_id, payload.atom_id)
    return {"log_id": log_id}


@router.post("/activity/end", response_model=dict, summary="Arrêter le suivi d'une activité")
def end_user_activity(
    payload: ActivityEndRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Clôture l'entrée de suivi identifiée par ``log_id``."""
    service = ProgressService(db=db, user_id=current_user.id)
    service.end_activity(payload.log_id)
    return {"status": "success"}


@router.get("/stats", response_model=UserStatsResponse, summary="Récupérer les statistiques globales")
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Expose les métriques agrégées (temps passé, streak)."""
    service = ProgressService(db=db, user_id=current_user.id)
    return service.get_user_stats()


@router.post(
    "/atom/{atom_id}/complete",
    status_code=status.HTTP_200_OK,
    summary="Marquer un atome (non interactif) comme terminé"
)
def mark_atom_completed(
    atom_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    atom = db.get(Atom, atom_id)
    if not atom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atome introuvable")

    progress_entry = (
        db.query(UserAtomProgress)
        .filter_by(user_id=current_user.id, atom_id=atom_id)
        .first()
    )
    if not progress_entry:
        progress_entry = UserAtomProgress(user_id=current_user.id, atom_id=atom_id)
        db.add(progress_entry)
        db.flush([progress_entry])

    progress_entry.attempts = (progress_entry.attempts or 0) + 1
    progress_entry.success_count = (progress_entry.success_count or 0) + 1
    progress_entry.status = 'completed'
    progress_entry.last_attempt_at = datetime.utcnow()
    if not progress_entry.completed_at:
        progress_entry.completed_at = datetime.utcnow()

    progress_service = ProgressService(db=db, user_id=current_user.id)
    capsule_progress = progress_service.record_atom_completion(atom_id)

    capsule_service = CapsuleService(db=db, user=current_user)
    snapshot = capsule_service.completion_snapshot(atom.molecule)

    db.commit()

    return {
        "status": progress_entry.status,
        "xp": capsule_progress.xp,
        **snapshot,
    }


@router.get(
    "/capsule/{capsule_id}",
    response_model=CapsuleProgressResponse,
    summary="Obtenir la progression d'une capsule"
)
def get_capsule_progress(
    capsule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CapsuleProgressResponse:
    """Retourne l'XP cumulée d'une capsule pour l'utilisateur connecté."""
    progress = (
        db.query(UserCapsuleProgress)
        .filter_by(user_id=current_user.id, capsule_id=capsule_id)
        .first()
    )

    xp = progress.xp if progress else 0
    return CapsuleProgressResponse(status="success", capsule_id=capsule_id, xp=xp)


@router.post("/log-answer", status_code=status.HTTP_201_CREATED, summary="Enregistrer la réponse d'un atome")
def log_user_answer(
    payload: AnswerLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Stocke la réponse brute de l'utilisateur pour diagnostic ou analytics."""
    atom = db.get(Atom, payload.atom_id)
    if not atom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atome introuvable")

    answer_log = UserAnswerLog(
        user_id=current_user.id,
        atom_id=payload.atom_id,
        is_correct=payload.is_correct,
        user_answer_json=payload.user_answer,
    )
    db.add(answer_log)
    db.flush()

    srs_service = SRSService(db=db, user=current_user)
    progress_entry = (
        db.query(UserAtomProgress)
        .filter_by(user_id=current_user.id, atom_id=payload.atom_id)
        .first()
    )
    if not progress_entry:
        progress_entry = UserAtomProgress(user_id=current_user.id, atom_id=payload.atom_id)
        db.add(progress_entry)
        db.flush([progress_entry])

    progress_entry.attempts = (progress_entry.attempts or 0) + 1
    progress_entry.last_attempt_at = datetime.utcnow()

    capsule_service = CapsuleService(db=db, user=current_user)

    if payload.is_correct:
        progress_entry.success_count = (progress_entry.success_count or 0) + 1
        progress_entry.status = 'completed'
        if not progress_entry.completed_at:
            progress_entry.completed_at = datetime.utcnow()
        ProgressService(db=db, user_id=current_user.id).record_atom_completion(payload.atom_id)
        srs_service.register_answer(atom, True)
    else:
        progress_entry.failure_count = (progress_entry.failure_count or 0) + 1
        progress_entry.status = 'failed'
        progress_entry.completed_at = None
        srs_service.register_answer(atom, False)

    db.commit()
    db.refresh(progress_entry)

    snapshot = capsule_service.completion_snapshot(atom.molecule)

    return {
        "status": progress_entry.status,
        "is_correct": payload.is_correct,
        **snapshot,
    }


@router.post("/atom/{atom_id}/reset", summary="Réinitialiser la progression d'un atome")
def reset_atom_progress(
    atom_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    atom = db.get(Atom, atom_id)
    if not atom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atome introuvable")

    progress_entry = (
        db.query(UserAtomProgress)
        .filter_by(user_id=current_user.id, atom_id=atom_id)
        .first()
    )
    if not progress_entry:
        progress_entry = UserAtomProgress(user_id=current_user.id, atom_id=atom_id)
        db.add(progress_entry)

    progress_entry.status = 'not_started'
    progress_entry.reset_count += 1
    progress_entry.last_attempt_at = datetime.utcnow()
    progress_entry.completed_at = None

    srs_service = SRSService(db=db, user=current_user)
    srs_service.register_reset(atom.molecule)
    db.commit()

    capsule_service = CapsuleService(db=db, user=current_user)
    snapshot = capsule_service.completion_snapshot(atom.molecule)

    return {
        "status": progress_entry.status,
        **snapshot,
    }
