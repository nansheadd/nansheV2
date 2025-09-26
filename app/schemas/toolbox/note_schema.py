from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MoleculeNoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=0)


class MoleculeNoteCreate(MoleculeNoteBase):
    molecule_id: int | None = Field(None, gt=0)


class MoleculeNoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=0)


class MoleculeNoteOut(BaseModel):
    id: int
    title: str
    content: str
    molecule_id: int | None
    molecule_title: Optional[str]
    capsule_id: Optional[int]
    capsule_title: Optional[str]
    capsule_domain: Optional[str]
    capsule_area: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
