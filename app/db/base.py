"""Déclare l'ensemble des modèles SQLAlchemy pour la détection automatique par Alembic."""

from app.db.base_class import Base

# Utilisateurs et notifications
from app.models.user.user_model import User
from app.models.user.notification_model import Notification
from app.models.user.badge_model import Badge, UserBadge

# Capsule & contenu pédagogique
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom
from app.models.capsule.language_roadmap_model import (
    LanguageRoadmap,
    LanguageRoadmapLevel,
    Skill,
    LevelSkillTarget,
    LevelFocus,
    LevelCheckpoint,
    LevelReward,
)
from app.models.capsule.utility_models import UserCapsuleEnrollment, UserCapsuleProgress

# Progression & activité
from app.models.progress.user_course_progress_model import UserCourseProgress
from app.models.progress.user_activity_log_model import UserActivityLog
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.progress.user_atomic_progress import (
    UserAtomProgress,
    UserCharacterProgress,
    UserVocabularyProgress,
)

# Analytics & feedback
from app.models.analytics.golden_examples_model import GoldenExample
from app.models.analytics.feedback_model import ContentFeedback
from app.models.analytics.vector_store_model import VectorStore
from app.models.analytics.classification_feedback_model import ClassificationFeedback
from app.models.analytics.ai_token_log_model import AITokenLog
from app.models.toolbox.molecule_note_model import MoleculeNote
from app.models.toolbox.coach_energy_model import CoachEnergyWallet
from app.models.toolbox.coach_conversation_model import (
    CoachConversationMessage,
    CoachConversationThread,
)
from app.models.vote.feature_vote_model import FeaturePoll, FeaturePollOption, FeaturePollVote

__all__ = (
    "Base",
    "User",
    "Notification",
    "Badge",
    "UserBadge",
    "Capsule",
    "Granule",
    "Molecule",
    "Atom",
    "LanguageRoadmap",
    "LanguageRoadmapLevel",
    "Skill",
    "LevelSkillTarget",
    "LevelFocus",
    "LevelCheckpoint",
    "LevelReward",
    "UserCapsuleEnrollment",
    "UserCapsuleProgress",
    "UserCourseProgress",
    "UserActivityLog",
    "UserAnswerLog",
    "UserAtomProgress",
    "UserCharacterProgress",
    "UserVocabularyProgress",
    "GoldenExample",
    "ContentFeedback",
    "VectorStore",
    "AITokenLog",
    "MoleculeNote",
    "ClassificationFeedback",
    "CoachEnergyWallet",
    "CoachConversationThread",
    "CoachConversationMessage",
    "FeaturePoll",
    "FeaturePollOption",
    "FeaturePollVote",
)
