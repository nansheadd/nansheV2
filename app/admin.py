"""Centralised configuration for the SQLAdmin back-office."""

from __future__ import annotations

import json
from typing import Any

from markupsafe import Markup
from sqladmin import ModelView

from app.models.analytics.ai_token_log_model import AITokenLog
from app.models.analytics.feedback_model import ContentFeedback
from app.models.capsule.atom_model import Atom
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.utility_models import UserCapsuleProgress, UserCapsuleEnrollment
from app.models.email.email_token import EmailToken
from app.models.progress.user_activity_log_model import UserActivityLog
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.user.badge_model import Badge, UserBadge
from app.models.user.notification_model import Notification
from app.models.user.user_model import User


def _json_preview(value: Any, *, max_chars: int = 160) -> Markup:
    """Render JSON content as a trimmed <pre> block for the admin."""
    if value in (None, ""):
        return Markup("<span style='color:#9ca3af;'>—</span>")

    if not isinstance(value, (dict, list)):
        text = str(value)
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, indent=2)
        except TypeError:
            text = str(value)

    truncated = text
    if len(text) > max_chars:
        truncated = text[:max_chars] + "…"

    return Markup(
        "<pre style='max-width:520px; white-space:pre-wrap; margin:0; font-size:12px;'>" + truncated + "</pre>"
    )


def _json_full(value: Any) -> Markup:
    return _json_preview(value, max_chars=10000)


try:
    _CAPSULE_PLAN_ATTR = getattr(Capsule, "learning_plan_json")
except AttributeError:
    _CAPSULE_PLAN_ATTR = None


class UserAdmin(ModelView, model=User):
    name = "Utilisateur"
    name_plural = "Utilisateurs"
    icon = "fa-solid fa-user"
    category = "Utilisateurs & Paiements"
    column_list = [
        User.id,
        User.username,
        User.email,
        User.subscription_status,
        User.is_email_verified,
        User.is_active,
        User.is_superuser,
        User.stripe_customer_id,
        User.created_at,
        User.last_login_at,
        User.account_deletion_requested_at,
        User.account_deletion_scheduled_at,
    ]
    column_searchable_list = [User.username, User.email, User.stripe_customer_id]
    column_sortable_list = [User.created_at, User.last_login_at]
    column_filters: list = []
    column_default_sort = [(User.created_at, True)]  # newest first
    column_labels = {
        User.is_email_verified: "Email vérifié",
        User.subscription_status: "Abonnement",
        User.stripe_customer_id: "Client Stripe",
        User.last_login_at: "Dernière connexion",
    }
    column_details_exclude_list = [User.hashed_password]
    column_formatters = {
        User.subscription_status: lambda m, _: m.subscription_status.value if m.subscription_status else "free",
    }
    form_excluded_columns = [
        "hashed_password",
        "enrollments",
        "capsule_progress",
        "course_progress",
        "activity_logs",
        "answer_logs",
        "notifications",
        "user_badges",
        "created_capsules",
        "roadmaps",
    ]
    can_export = True
    page_size = 50


class CapsuleAdmin(ModelView, model=Capsule):
    name = "Capsule"
    name_plural = "Capsules"
    icon = "fa-solid fa-book"
    category = "Contenus"
    column_list = [
        Capsule.id,
        Capsule.title,
        Capsule.domain,
        Capsule.area,
        Capsule.main_skill,
        Capsule.generation_status,
        Capsule.creator,
    ]
    column_searchable_list = [Capsule.title, Capsule.main_skill, Capsule.domain, Capsule.area]
    column_filters: list = []
    column_default_sort = [Capsule.id]
    column_labels = {
        Capsule.main_skill: "Compétence principale",
        Capsule.generation_status: "Statut",
    }
    form_ajax_refs = {
        "creator": {"fields": ("username", "email")},
    }
    can_export = True
    if _CAPSULE_PLAN_ATTR is not None:
        column_exclude_list = [_CAPSULE_PLAN_ATTR]
        column_formatters_detail = {
            _CAPSULE_PLAN_ATTR: lambda m, _: _json_full(getattr(m, "learning_plan_json", None)),
        }


class GranuleAdmin(ModelView, model=Granule):
    name = "Granule"
    name_plural = "Granules"
    icon = "fa-solid fa-layer-group"
    category = "Contenus"
    column_list = [Granule.id, Granule.capsule, Granule.title, Granule.order]
    column_searchable_list = [Granule.title]
    column_filters: list = []
    form_ajax_refs = {"capsule": {"fields": ("title", "main_skill")}}
    can_export = True


class MoleculeAdmin(ModelView, model=Molecule):
    name = "Molécule"
    name_plural = "Molécules"
    icon = "fa-solid fa-diagram-project"
    category = "Contenus"
    column_list = [Molecule.id, Molecule.granule, Molecule.title, Molecule.order]
    column_searchable_list = [Molecule.title]
    column_filters: list = []
    form_ajax_refs = {"granule": {"fields": ("title",)}}
    can_export = True


class AtomAdmin(ModelView, model=Atom):
    name = "Atome"
    name_plural = "Atomes"
    icon = "fa-solid fa-atom"
    category = "Contenus"
    column_list = [Atom.id, Atom.molecule, Atom.title, Atom.content_type, Atom.difficulty]
    column_searchable_list = [Atom.title]
    column_filters: list = []
    column_formatters = {
        Atom.content: lambda m, _: _json_preview(m.content),
    }
    column_formatters_detail = {
        Atom.content: lambda m, _: _json_full(m.content),
    }
    form_ajax_refs = {"molecule": {"fields": ("title",)}}
    form_excluded_columns = []
    can_export = True


class UserCapsuleProgressAdmin(ModelView, model=UserCapsuleProgress):
    name = "Progression Capsule"
    name_plural = "Progressions Capsule"
    icon = "fa-solid fa-chart-line"
    category = "Utilisateurs & Paiements"
    column_list = [
        UserCapsuleProgress.user,
        UserCapsuleProgress.capsule,
        UserCapsuleProgress.skill_id,
        UserCapsuleProgress.xp,
        UserCapsuleProgress.strength,
    ]
    column_filters: list = []
    can_export = True


class UserCapsuleEnrollmentAdmin(ModelView, model=UserCapsuleEnrollment):
    name = "Inscriptions"
    name_plural = "Inscriptions"
    icon = "fa-solid fa-users"
    category = "Utilisateurs & Paiements"
    column_list = [UserCapsuleEnrollment.user, UserCapsuleEnrollment.capsule]
    can_export = True


class UserAnswerLogAdmin(ModelView, model=UserAnswerLog):
    name = "Réponse"
    name_plural = "Réponses"
    icon = "fa-solid fa-comments"
    category = "Apprentissage"
    column_list = [
        UserAnswerLog.user,
        UserAnswerLog.atom,
        UserAnswerLog.is_correct,
        UserAnswerLog.created_at,
    ]
    column_filters: list = []
    column_default_sort = [(UserAnswerLog.created_at, True)]
    can_export = True


class UserActivityLogAdmin(ModelView, model=UserActivityLog):
    name = "Activité"
    name_plural = "Activités"
    icon = "fa-solid fa-stopwatch"
    category = "Apprentissage"
    column_list = [
        UserActivityLog.user,
        UserActivityLog.capsule_id,
        UserActivityLog.atom_id,
        UserActivityLog.start_time,
        UserActivityLog.end_time,
    ]
    column_default_sort = [(UserActivityLog.start_time, True)]
    can_export = True


class AITokenLogAdmin(ModelView, model=AITokenLog):
    name = "Log Tokens"
    name_plural = "Logs Tokens"
    icon = "fa-solid fa-robot"
    category = "Tech & Diagnostique"
    column_list = [
        AITokenLog.user,
        AITokenLog.timestamp,
        AITokenLog.feature,
        AITokenLog.model_name,
        AITokenLog.prompt_tokens,
        AITokenLog.completion_tokens,
        AITokenLog.cost_usd,
    ]
    column_default_sort = [(AITokenLog.timestamp, True)]
    can_export = True


class FeedbackAdmin(ModelView, model=ContentFeedback):
    name = "Feedback"
    name_plural = "Feedbacks"
    icon = "fa-solid fa-thumbs-up"
    category = "Apprentissage"
    column_list = [
        ContentFeedback.user,
        ContentFeedback.content_type,
        ContentFeedback.content_id,
        ContentFeedback.rating,
        ContentFeedback.status,
    ]
    column_filters: list = []
    can_export = True


class NotificationAdmin(ModelView, model=Notification):
    name = "Notification"
    name_plural = "Notifications"
    icon = "fa-solid fa-bell"
    category = "Utilisateurs & Paiements"
    column_list = [
        Notification.user,
        Notification.category,
        Notification.status,
        Notification.title,
        Notification.created_at,
    ]
    column_filters: list = []
    column_searchable_list = [Notification.title, Notification.message]
    column_default_sort = [(Notification.created_at, True)]
    column_formatters = {
        Notification.message: lambda m, _: Markup(f"<small>{m.message}</small>"),
    }
    can_export = True


class EmailTokenAdmin(ModelView, model=EmailToken):
    name = "Jeton Email"
    name_plural = "Jetons Email"
    icon = "fa-solid fa-envelope"
    category = "Sécurité"
    column_list = [
        EmailToken.user,
        EmailToken.purpose,
        EmailToken.token,
        EmailToken.expires_at,
        EmailToken.used_at,
    ]
    column_default_sort = [(EmailToken.created_at, True)]
    column_filters: list = []
    column_searchable_list = [EmailToken.token]
    column_formatters = {
        EmailToken.token: lambda m, _: Markup(f"<code>{m.token[:10]}…</code>"),
    }
    column_formatters_detail = {
        EmailToken.token: lambda m, _: Markup(f"<code>{m.token}</code>"),
    }
    can_export = True


class BadgeAdmin(ModelView, model=Badge):
    name = "Badge"
    name_plural = "Badges"
    icon = "fa-solid fa-award"
    category = "Gamification"
    column_list = [Badge.id, Badge.name, Badge.slug, Badge.category, Badge.points]
    column_searchable_list = [Badge.name, Badge.slug]
    column_filters: list = []
    can_export = True


class UserBadgeAdmin(ModelView, model=UserBadge):
    name = "Badge utilisateur"
    name_plural = "Badges utilisateur"
    icon = "fa-solid fa-medal"
    category = "Gamification"
    column_list = [UserBadge.user, UserBadge.badge, UserBadge.awarded_at]
    column_default_sort = [(UserBadge.awarded_at, True)]
    can_export = True
