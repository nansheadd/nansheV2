"""SQLAdmin configuration limited to Capsule-centric models."""

from sqladmin import ModelView

from app.models.analytics.ai_token_log_model import AITokenLog
from app.models.analytics.feedback_model import ContentFeedback
from app.models.capsule.atom_model import Atom
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.utility_models import UserCapsuleProgress, UserCapsuleEnrollment
from app.models.progress.user_activity_log_model import UserActivityLog
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.user.user_model import User


class UserAdmin(ModelView, model=User):
    name = "Utilisateur"
    name_plural = "Utilisateurs"
    icon = "fa-solid fa-user"
    column_list = [User.id, User.username, User.email, User.created_at, User.is_active]
    column_searchable_list = [User.username, User.email]


class CapsuleAdmin(ModelView, model=Capsule):
    name = "Capsule"
    name_plural = "Capsules"
    icon = "fa-solid fa-book"
    column_list = [
        Capsule.id,
        Capsule.title,
        Capsule.domain,
        Capsule.area,
        Capsule.main_skill,
        Capsule.generation_status,
    ]
    column_searchable_list = [Capsule.title, Capsule.main_skill]


class GranuleAdmin(ModelView, model=Granule):
    name = "Granule"
    name_plural = "Granules"
    icon = "fa-solid fa-layer-group"
    column_list = [Granule.id, Granule.capsule, Granule.title, Granule.order]
    column_searchable_list = [Granule.title]


class MoleculeAdmin(ModelView, model=Molecule):
    name = "Molécule"
    name_plural = "Molécules"
    icon = "fa-solid fa-diagram-project"
    column_list = [Molecule.id, Molecule.granule, Molecule.title, Molecule.order]
    column_searchable_list = [Molecule.title]


class AtomAdmin(ModelView, model=Atom):
    name = "Atome"
    name_plural = "Atomes"
    icon = "fa-solid fa-atom"
    column_list = [Atom.id, Atom.molecule, Atom.title, Atom.content_type, Atom.difficulty]
    column_searchable_list = [Atom.title]


class UserCapsuleProgressAdmin(ModelView, model=UserCapsuleProgress):
    name = "Progression Capsule"
    name_plural = "Progressions Capsule"
    icon = "fa-solid fa-chart-line"
    column_list = [
        UserCapsuleProgress.user,
        UserCapsuleProgress.capsule,
        UserCapsuleProgress.skill_id,
        UserCapsuleProgress.xp,
        UserCapsuleProgress.strength,
    ]


class UserCapsuleEnrollmentAdmin(ModelView, model=UserCapsuleEnrollment):
    name = "Inscriptions"
    name_plural = "Inscriptions"
    icon = "fa-solid fa-users"
    column_list = [UserCapsuleEnrollment.user, UserCapsuleEnrollment.capsule]


class UserAnswerLogAdmin(ModelView, model=UserAnswerLog):
    name = "Réponses"
    name_plural = "Réponses"
    icon = "fa-solid fa-comments"
    column_list = [
        UserAnswerLog.user,
        UserAnswerLog.atom,
        UserAnswerLog.is_correct,
        UserAnswerLog.created_at,
    ]


class UserActivityLogAdmin(ModelView, model=UserActivityLog):
    name = "Activités"
    name_plural = "Activités"
    icon = "fa-solid fa-stopwatch"
    column_list = [
        UserActivityLog.user,
        UserActivityLog.capsule_id,
        UserActivityLog.atom_id,
        UserActivityLog.start_time,
        UserActivityLog.end_time,
    ]


class AITokenLogAdmin(ModelView, model=AITokenLog):
    name = "Logs Tokens"
    name_plural = "Logs Tokens"
    icon = "fa-solid fa-robot"
    column_list = [
        AITokenLog.user,
        AITokenLog.timestamp,
        AITokenLog.feature,
        AITokenLog.model_name,
        AITokenLog.prompt_tokens,
        AITokenLog.completion_tokens,
        AITokenLog.cost_usd,
    ]


class FeedbackAdmin(ModelView, model=ContentFeedback):
    name = "Feedback"
    name_plural = "Feedbacks"
    icon = "fa-solid fa-thumbs-up"
    column_list = [
        ContentFeedback.user,
        ContentFeedback.content_type,
        ContentFeedback.content_id,
        ContentFeedback.rating,
        ContentFeedback.status,
    ]
