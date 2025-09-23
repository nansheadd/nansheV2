"""Centralised configuration for the SQLAdmin back-office."""

from __future__ import annotations

import json
import textwrap
from typing import Any

from markupsafe import Markup
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.requests import Request
from starlette.responses import Response
from sqladmin import Admin, BaseView, ModelView, expose
from sqladmin.authentication import login_required

from app.db.session import async_engine
from app.models.analytics.ai_token_log_model import AITokenLog
from app.models.analytics.classification_feedback_model import (
    ClassificationFeedback,
)
from app.models.analytics.feedback_model import ContentFeedback, ContentFeedbackDetail
from app.models.capsule.atom_model import Atom
from app.models.capsule.capsule_model import Capsule, GenerationStatus
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.utility_models import UserCapsuleProgress, UserCapsuleEnrollment
from app.models.email.email_token import EmailToken
from app.models.progress.user_activity_log_model import UserActivityLog
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.user.badge_model import Badge, UserBadge
from app.models.user.notification_model import Notification
from app.models.user.user_model import SubscriptionStatus, User


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


_ASYNC_SESSION_FACTORY = async_sessionmaker(async_engine, expire_on_commit=False)


def _safe_int(value: Any) -> int:
    """Convert SQL numeric values to plain integers."""

    if value in (None, ""):
        return 0

    if isinstance(value, bool):
        return int(value)

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _percentage(part: int, total: int) -> float:
    if not total:
        return 0.0
    return round((part / total) * 100.0, 1)


def _shorten(value: str | None, width: int = 90) -> str | None:
    if not value:
        return None
    return textwrap.shorten(value, width=width, placeholder="…")


def _rating_badge(rating: str | None) -> str:
    if rating == "liked":
        return "bg-success"
    if rating == "disliked":
        return "bg-danger"
    return "bg-secondary"


def _status_badge(status: str | None) -> str:
    if status == "pending":
        return "bg-warning"
    if status in {"approved", "resolved", "closed"}:
        return "bg-success"
    if status in {"rejected", "failed"}:
        return "bg-danger"
    return "bg-secondary"


async def _collect_dashboard_metrics() -> dict[str, Any]:
    async with _ASYNC_SESSION_FACTORY() as session:
        feedback_result = await session.execute(
            select(
                func.count(ContentFeedback.id),
                func.count().filter(ContentFeedback.rating == "liked"),
                func.count().filter(ContentFeedback.rating == "disliked"),
                func.count().filter(ContentFeedback.status == "pending"),
                func.count().filter(ContentFeedback.status == "approved"),
                func.count().filter(ContentFeedback.status == "rejected"),
            )
        )

        (
            feedback_total,
            feedback_liked,
            feedback_disliked,
            feedback_pending,
            feedback_approved,
            feedback_rejected,
        ) = (_safe_int(value) for value in feedback_result.one())

        capsule_result = await session.execute(
            select(
                func.count(Capsule.id),
                func.count().filter(Capsule.generation_status == GenerationStatus.COMPLETED),
                func.count().filter(Capsule.generation_status == GenerationStatus.PENDING),
                func.count().filter(Capsule.generation_status == GenerationStatus.FAILED),
            )
        )

        (
            capsule_total,
            capsule_completed,
            capsule_pending,
            capsule_failed,
        ) = (_safe_int(value) for value in capsule_result.one())

        problem_result = await session.execute(
            select(
                func.count(ClassificationFeedback.id),
                func.count().filter(ClassificationFeedback.is_correct.is_(False)),
                func.count().filter(ClassificationFeedback.is_correct.is_(True)),
            )
        )

        (
            problem_total,
            problem_open,
            problem_resolved,
        ) = (_safe_int(value) for value in problem_result.one())

        payments_result = await session.execute(
            select(
                func.count(User.id),
                func.count().filter(User.subscription_status == SubscriptionStatus.PREMIUM),
                func.count().filter(User.subscription_status == SubscriptionStatus.FREE),
                func.count().filter(User.subscription_status == SubscriptionStatus.CANCELED),
                func.count().filter(User.stripe_customer_id.is_not(None)),
            )
        )

        (
            users_total,
            users_premium,
            users_free,
            users_canceled,
            users_stripe_linked,
        ) = (_safe_int(value) for value in payments_result.one())

        feedback_rows = await session.execute(
            select(
                ContentFeedback.id,
                ContentFeedback.content_type,
                ContentFeedback.content_id,
                ContentFeedback.rating,
                ContentFeedback.status,
                User.username,
                ContentFeedbackDetail.reason_code,
                ContentFeedbackDetail.comment,
            )
            .join(User, ContentFeedback.user_id == User.id, isouter=True)
            .join(
                ContentFeedbackDetail,
                ContentFeedbackDetail.feedback_id == ContentFeedback.id,
                isouter=True,
            )
            .where(
                or_(
                    ContentFeedback.rating == "disliked",
                    ContentFeedback.status == "pending",
                )
            )
            .order_by(ContentFeedback.id.desc())
            .limit(5)
        )

        recent_feedback = []
        for row in feedback_rows:
            data = row._mapping
            rating_value = data["rating"]
            status_value = data["status"]
            rating_label = (
                "Positif"
                if rating_value == "liked"
                else "Négatif"
                if rating_value == "disliked"
                else rating_value
                or "—"
            )
            status_label = {
                "pending": "À traiter",
                "approved": "Validé",
                "rejected": "Rejeté",
            }.get(status_value, status_value or "—")
            recent_feedback.append(
                {
                    "id": _safe_int(data["id"]),
                    "user": data["username"] or "—",
                    "content": f"{data['content_type']} #{data['content_id']}",
                    "rating": rating_value,
                    "rating_badge": _rating_badge(rating_value),
                    "rating_label": rating_label,
                    "status": status_value,
                    "status_badge": _status_badge(status_value),
                    "status_label": status_label,
                    "reason": data.get("reason_code") or "—",
                    "comment": _shorten(data.get("comment"), 120),
                }
            )

        problem_rows = await session.execute(
            select(
                ClassificationFeedback.id,
                ClassificationFeedback.input_text,
                ClassificationFeedback.final_domain,
                ClassificationFeedback.final_area,
                ClassificationFeedback.predicted_domain,
                ClassificationFeedback.created_at,
                User.username,
            )
            .join(User, ClassificationFeedback.user_id == User.id, isouter=True)
            .where(ClassificationFeedback.is_correct.is_(False))
            .order_by(desc(ClassificationFeedback.created_at))
            .limit(5)
        )

        recent_problems = []
        for row in problem_rows:
            data = row._mapping
            created_at = data.get("created_at")
            recent_problems.append(
                {
                    "id": _safe_int(data["id"]),
                    "user": data["username"] or "—",
                    "domain": data.get("final_domain"),
                    "area": data.get("final_area"),
                    "predicted": data.get("predicted_domain"),
                    "excerpt": _shorten(data.get("input_text"), 120),
                    "created": created_at.strftime("%d/%m %H:%M") if created_at else "—",
                    "status_label": "À traiter",
                    "status_badge": "bg-warning",
                }
            )

    feedback_approval_rate = _percentage(feedback_liked, feedback_total)
    capsules_completion_rate = _percentage(capsule_completed, capsule_total)
    problems_resolution_rate = _percentage(problem_resolved, problem_total)
    premium_rate = _percentage(users_premium, users_total)
    stripe_rate = _percentage(users_stripe_linked, users_total)

    feedback_stats = {
        "total": feedback_total,
        "liked": feedback_liked,
        "disliked": feedback_disliked,
        "pending": feedback_pending,
        "approved": feedback_approved,
        "rejected": feedback_rejected,
        "approval_rate": feedback_approval_rate,
        "breakdown": [
            {
                "label": "Positifs",
                "value": feedback_liked,
                "ratio": feedback_approval_rate,
                "color": "bg-success",
            },
            {
                "label": "Négatifs",
                "value": feedback_disliked,
                "ratio": _percentage(feedback_disliked, feedback_total),
                "color": "bg-danger",
            },
            {
                "label": "En attente",
                "value": feedback_pending,
                "ratio": _percentage(feedback_pending, feedback_total),
                "color": "bg-warning",
            },
        ],
        "recent": recent_feedback,
    }

    capsule_stats = {
        "total": capsule_total,
        "completed": capsule_completed,
        "pending": capsule_pending,
        "failed": capsule_failed,
        "completion_rate": capsules_completion_rate,
        "breakdown": [
            {
                "label": "Terminées",
                "value": capsule_completed,
                "ratio": capsules_completion_rate,
                "color": "bg-success",
            },
            {
                "label": "En production",
                "value": capsule_pending,
                "ratio": _percentage(capsule_pending, capsule_total),
                "color": "bg-primary",
            },
            {
                "label": "En échec",
                "value": capsule_failed,
                "ratio": _percentage(capsule_failed, capsule_total),
                "color": "bg-danger",
            },
        ],
    }

    problem_stats = {
        "total": problem_total,
        "open": problem_open,
        "resolved": problem_resolved,
        "resolution_rate": problems_resolution_rate,
        "recent": recent_problems,
    }

    payment_stats = {
        "total_users": users_total,
        "premium": users_premium,
        "free": users_free,
        "canceled": users_canceled,
        "premium_rate": premium_rate,
        "stripe_linked": users_stripe_linked,
        "stripe_rate": stripe_rate,
        "breakdown": [
            {
                "label": "Premium",
                "value": users_premium,
                "ratio": premium_rate,
                "color": "bg-success",
            },
            {
                "label": "Gratuit",
                "value": users_free,
                "ratio": _percentage(users_free, users_total),
                "color": "bg-primary",
            },
            {
                "label": "Annulé",
                "value": users_canceled,
                "ratio": _percentage(users_canceled, users_total),
                "color": "bg-warning",
            },
        ],
    }

    summary_cards = [
        {
            "title": "Feedbacks",
            "icon": "fa-regular fa-comments",
            "value": feedback_total,
            "subtitle": f"{feedback_approval_rate:.1f}% positifs",
        },
        {
            "title": "Capsules",
            "icon": "fa-solid fa-graduation-cap",
            "value": capsule_total,
            "subtitle": f"{capsule_completed} terminées",
        },
        {
            "title": "Problèmes",
            "icon": "fa-solid fa-triangle-exclamation",
            "value": problem_open,
            "subtitle": f"{problem_total} signalements",
        },
        {
            "title": "Paiements",
            "icon": "fa-solid fa-credit-card",
            "value": users_premium,
            "subtitle": f"{premium_rate:.1f}% premium",
        },
    ]

    return {
        "summary": summary_cards,
        "feedback": feedback_stats,
        "capsules": capsule_stats,
        "problems": problem_stats,
        "payments": payment_stats,
    }


async def _render_dashboard(request: Request, templates) -> Response:
    context = await _collect_dashboard_metrics()
    context.update(
        {
            "request": request,
            "title": "Tableau de bord",
            "subtitle": "Suivi des indicateurs clés",
        }
    )
    return await templates.TemplateResponse(
        request,
        "sqladmin/dashboard.html",
        context,
    )


class DashboardView(BaseView):
    name = "Tableau de bord"
    icon = "fa-solid fa-gauge-high"

    @expose("/dashboard", methods=["GET"], identity="dashboard")
    async def dashboard(self, request: Request) -> Response:
        return await _render_dashboard(request, self.templates)


class BackOfficeAdmin(Admin):
    @login_required
    async def index(self, request: Request) -> Response:
        return await _render_dashboard(request, self.templates)


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
