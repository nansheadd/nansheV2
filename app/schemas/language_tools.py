from __future__ import annotations

from typing import Dict, List, Optional, Literal

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


class VocabularyWordOut(BaseModel):
    vocabulary_id: str
    term: str
    translation_fr: str
    transliteration: Optional[str] = None
    example: Optional[str] = None
    example_translation: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    ipa: Optional[str] = None
    strength_target_to_fr: float = Field(0.0, ge=0.0, le=1.0)
    strength_fr_to_target: float = Field(0.0, ge=0.0, le=1.0)


class VocabularySetOut(BaseModel):
    name: str
    notes: Optional[str] = None
    capsule_id: Optional[int] = None
    molecule_id: Optional[int] = None
    words: List[VocabularyWordOut]


class VocabularyPracticeSummaryOut(BaseModel):
    target_to_fr: PracticeModeSummaryOut
    fr_to_target: PracticeModeSummaryOut


class VocabularyTrainerResponse(BaseModel):
    language: str
    language_code: Optional[str] = None
    vocabulary_sets: List[VocabularySetOut]
    practice_summary: VocabularyPracticeSummaryOut


class VocabularySessionItem(BaseModel):
    vocabulary_id: str
    direction: str = Field(pattern="^(target_to_fr|fr_to_target)$")
    success: bool


class VocabularySessionCreate(BaseModel):
    items: List[VocabularySessionItem]


class DialogueHistoryTurn(BaseModel):
    speaker: Literal["user", "assistant"]
    message: str


class DialoguePracticeRequest(BaseModel):
    language: str
    language_code: Optional[str] = None
    scenario: str
    cefr: Optional[str] = None
    history: List[DialogueHistoryTurn] = Field(default_factory=list)
    user_message: str
    focus_vocabulary: List[VocabularyWordOut] = Field(default_factory=list)


class DialoguePracticeResponse(BaseModel):
    reply_tl: str
    reply_transliteration: Optional[str] = None
    reply_translation_fr: Optional[str] = None
    feedback_fr: Optional[str] = None
    suggested_keywords: List[str] = Field(default_factory=list)
