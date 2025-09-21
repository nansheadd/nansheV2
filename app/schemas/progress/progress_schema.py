"""Schémas Pydantic pour les endpoints de progression capsule-first."""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class ActivityStartRequest(BaseModel):
    """Données nécessaires pour démarrer le suivi d'une activité."""

    capsule_id: int
    atom_id: int | None = None


class ActivityEndRequest(BaseModel):
    """Données nécessaires pour arrêter un suivi en cours."""

    log_id: int


class AnswerLogCreate(BaseModel):
    """Payload minimal pour enregistrer la réponse d'un utilisateur à un atome."""

    atom_id: int
    is_correct: bool
    # On conserve l'alias historique "answer" pour la compatibilité frontend
    user_answer: Dict[str, Any] = Field(..., alias="answer")


class CapsuleProgressResponse(BaseModel):
    """Structure de réponse renvoyée après mise à jour de progression."""

    status: str
    capsule_id: int
    xp: int


class DomainStudyEntry(BaseModel):
    domain: str
    seconds: int


class AreaStudyEntry(BaseModel):
    domain: str
    area: str
    seconds: int


class CapsuleStudyEntry(BaseModel):
    capsule_id: int
    title: str
    domain: str
    area: str
    seconds: int


class StudyBreakdown(BaseModel):
    by_domain: List[DomainStudyEntry] = Field(default_factory=list)
    by_area: List[AreaStudyEntry] = Field(default_factory=list)
    by_capsule: List[CapsuleStudyEntry] = Field(default_factory=list)


class UserStatsResponse(BaseModel):
    total_study_time_seconds: int = 0
    current_streak_days: int = 0
    total_sessions: int = 0
    breakdown: StudyBreakdown = Field(default_factory=StudyBreakdown)
