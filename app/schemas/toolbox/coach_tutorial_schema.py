"""Pydantic schemas for coach tutorial state tracking."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TutorialStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class CoachTutorialStateOut(BaseModel):
    tutorial_key: str
    status: TutorialStatus
    last_step_index: int | None = Field(default=None, ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime

    class Config:
        from_attributes = True


class CoachTutorialStateUpdate(BaseModel):
    status: TutorialStatus | None = None
    last_step_index: int | None = Field(default=None, ge=-1)
