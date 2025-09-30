"""Schemas pour les fonctionnalités de la toolbox."""

from .note_schema import MoleculeNoteBase, MoleculeNoteCreate, MoleculeNoteUpdate, MoleculeNoteOut
from .coach_conversation_schema import (
    CoachConversationMessageOut,
    CoachConversationThreadDetail,
    CoachConversationThreadList,
    CoachConversationThreadOut,
)
from .coach_tutorial_schema import (
    CoachTutorialStateOut,
    CoachTutorialStateUpdate,
    TutorialStatus,
)

__all__ = (
    "MoleculeNoteBase",
    "MoleculeNoteCreate",
    "MoleculeNoteUpdate",
    "MoleculeNoteOut",
    "CoachConversationMessageOut",
    "CoachConversationThreadOut",
    "CoachConversationThreadDetail",
    "CoachConversationThreadList",
    "CoachTutorialStateOut",
    "CoachTutorialStateUpdate",
    "TutorialStatus",
)
