"""Admin views for SQLAdmin with automatic model registration."""

import importlib
from pathlib import Path

from sqladmin import ModelView
from sqladmin.filters import ForeignKeyFilter, StaticValuesFilter
from wtforms import SelectField

from app.db.base_class import Base
from app.models.analytics.ai_token_log_model import AITokenLog
from app.models.analytics.feedback_model import (
    ContentFeedback,
    FeedbackRating,
    FeedbackStatus,
)
from app.models.course.course_model import Course
from app.models.user.user_model import User


class UserAdmin(ModelView, model=User):
    """Admin view for the User model."""

    name = "Utilisateur"
    name_plural = "Utilisateurs"
    icon = "fa-solid fa-user"
    column_list = [
        User.id,
        User.username,
        User.email,
        User.is_active,
        User.is_superuser,
        User.created_at,
    ]
    column_searchable_list = [User.username, User.email]
    form_columns = [
        User.username,
        User.email,
        User.full_name,
        User.is_active,
        User.is_superuser,
    ]
    can_create = True
    can_edit = True
    can_delete = True


class CourseAdmin(ModelView, model=Course):
    """Admin view for the Course model."""

    name = "Cours"
    name_plural = "Cours"
    icon = "fa-solid fa-book"
    column_list = [
        Course.id,
        Course.title,
        Course.course_type,
        Course.generation_status,
        Course.model_choice,
    ]
    column_searchable_list = [Course.title]
    can_create = True
    can_edit = True
    can_delete = True


class AITokenLogAdmin(ModelView, model=AITokenLog):
    """Admin view for AI token usage logs."""

    name = "Log de Tokens"
    name_plural = "Logs de Tokens"
    icon = "fa-solid fa-robot"
    column_list = [
        AITokenLog.id,
        AITokenLog.user_id,
        AITokenLog.timestamp,
        AITokenLog.feature,
        AITokenLog.model_name,
        AITokenLog.prompt_tokens,
        AITokenLog.completion_tokens,
        AITokenLog.cost_usd,
    ]
    column_searchable_list = [AITokenLog.feature]
    can_create = True
    can_edit = True
    can_delete = True


class FeedbackAdmin(ModelView, model=ContentFeedback):
    """Admin view for user feedback on generated content."""

    name = "Feedback Contenu"
    name_plural = "Feedbacks Contenu"
    icon = "fa-solid fa-thumbs-up"

    column_list = [
        ContentFeedback.id,
        ContentFeedback.content_type,
        ContentFeedback.content_id,
        ContentFeedback.rating,
        ContentFeedback.status,
        ContentFeedback.user,
    ]

    column_formatters = {
        ContentFeedback.user: lambda m, a: m.user.username if m.user else "",
    }

    column_searchable_list = [ContentFeedback.content_type]

    column_filters = [
        StaticValuesFilter(
            ContentFeedback.status,
            values=["pending", "approved", "rejected"],
            title="Statut",
        ),
        StaticValuesFilter(
            ContentFeedback.rating,
            values=["liked", "disliked"],
            title="Évaluation",
        ),
        ForeignKeyFilter(ContentFeedback.user_id, User.username, title="Utilisateur"),
    ]

    column_editable_list = ["status"]
    form_columns = ["status"]

    form_overrides = {
        "status": SelectField,
    }
    form_args = {
        "status": {
            "choices": [
                ("pending", "pending"),
                ("approved", "approved"),
                ("rejected", "rejected"),
            ],
            "coerce": str,
        },
    }

    can_create = True
    can_edit = True
    can_delete = True


def register_all_models(admin) -> None:
    """Register every SQLAlchemy model with the admin interface.

    This dynamically imports all ``*_model.py`` files under ``app/models`` so that
    SQLAlchemy is aware of every model. Any model not explicitly registered above
    will get a default ``ModelView`` allowing full CRUD access.
    """

    models_path = Path(__file__).resolve().parent / "models"
    for path in models_path.rglob("*_model.py"):
        module = "app.models." + ".".join(path.relative_to(models_path).with_suffix("").parts)
        importlib.import_module(module)

    excluded = {User, Course, AITokenLog, ContentFeedback}

    meta = type(ModelView)
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if model in excluded:
            continue
        view = meta(f"{model.__name__}Admin", (ModelView,), {}, model=model)
        admin.add_view(view)

