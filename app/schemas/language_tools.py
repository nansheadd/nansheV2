from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class CharacterEntryOut(BaseModel):
    character_id: str
    symbol: str
    romanization: str | None = None
    ipa: str | None = None
    category: str | None = None
    strength_read: float = Field(0.0, ge=0.0, le=1.0)
    strength_write: float = Field(0.0, ge=0.0, le=1.0)


class CharacterSetOut(BaseModel):
    name: str
    notes: str | None = None
    characters: List[CharacterEntryOut]


class PracticeModeSummaryOut(BaseModel):
    mastered: int
    total: int
    progress: float


class PracticeSummaryOut(BaseModel):
    read: PracticeModeSummaryOut
    write: PracticeModeSummaryOut


class CharacterTrainerResponse(BaseModel):
    language: str
    language_code: str | None = None
    character_sets: List[CharacterSetOut]
    practice_summary: PracticeSummaryOut
    virtual_keyboard: List[str]
    transliteration_map: Dict[str, str]


class CharacterSessionItem(BaseModel):
    character_id: str
    mode: str = Field(pattern="^(read|write)$")
    success: bool


class CharacterSessionCreate(BaseModel):
    items: List[CharacterSessionItem]


class AvailableLanguageOut(BaseModel):
    key: str
    label: str
    code: str
    capsule_ids: List[int] = Field(default_factory=list)
