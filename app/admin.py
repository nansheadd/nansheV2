"""Admin views for SQLAdmin with automatic model registration."""
from app.db.base import *

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
from app.models.course.level_model import Level
from app.models.course.chapter_model import Chapter
from app.models.course.vocabulary_item_model import VocabularyItem
from app.models.course.grammar_rule_model import GrammarRule
from app.models.course.knowledge_component_model import KnowledgeComponent
from app.models.course.knowledge_graph_model import (
    KnowledgeEdge,
    KnowledgeNode,
    NodeExercise,
)
from app.models.progress.user_course_progress_model import UserCourseProgress
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
        AITokenLog.user,
        AITokenLog.timestamp,
        AITokenLog.feature,
        AITokenLog.model_name,
        AITokenLog.prompt_tokens,
        AITokenLog.completion_tokens,
        AITokenLog.cost_usd,
    ]

    column_formatters = {
        AITokenLog.user: lambda m, a: m.user.username if m.user else "",
    }

    column_filters = [ForeignKeyFilter(AITokenLog.user_id, User.username, title="Utilisateur")]
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


class LevelAdmin(ModelView, model=Level):
    """Admin view for course levels."""

    name = "Niveau"
    name_plural = "Niveaux"
    icon = "fa-solid fa-layer-group"
    column_list = [
        Level.id,
        Level.title,
        Level.level_order,
        Level.are_chapters_generated,
        Level.course,
    ]

    column_formatters = {
        Level.course: lambda m, a: m.course.title if m.course else "",
    }

    column_searchable_list = [Level.title]
    can_create = True
    can_edit = True
    can_delete = True


class ChapterAdmin(ModelView, model=Chapter):
    """Admin view for chapters."""

    name = "Chapitre"
    name_plural = "Chapitres"
    icon = "fa-solid fa-book-open"
    column_list = [
        Chapter.id,
        Chapter.title,
        Chapter.chapter_order,
        Chapter.lesson_status,
        Chapter.exercises_status,
        Chapter.level,
    ]

    column_formatters = {
        Chapter.level: lambda m, a: m.level.title if m.level else "",
    }

    column_searchable_list = [Chapter.title]
    can_create = True
    can_edit = True
    can_delete = True


class VocabularyItemAdmin(ModelView, model=VocabularyItem):
    name = "Vocabulary Item"
    name_plural = "Vocabulary Items"
    icon = "fa-solid fa-list-alt"
    category = "Course Content"

    # V-- LA CORRECTION EST ICI --V
    # Remplacez .term par .word
    column_list = [
        VocabularyItem.id,
        VocabularyItem.word, # C'était VocabularyItem.term
        VocabularyItem.translation,
        VocabularyItem.chapter,
    ]
    column_searchable_list = [VocabularyItem.word, VocabularyItem.translation]
    form_columns = [
        VocabularyItem.chapter,
        VocabularyItem.word,
        VocabularyItem.pinyin,
        VocabularyItem.translation,
    ]

class GrammarRuleAdmin(ModelView, model=GrammarRule):
    """Admin view for grammar rules."""

    name = "Règle de grammaire"
    name_plural = "Règles de grammaire"
    icon = "fa-solid fa-scroll"
    column_list = [
        GrammarRule.id,
        GrammarRule.rule_name,
        GrammarRule.explanation,
        GrammarRule.example_sentence,
        GrammarRule.chapter,
    ]

    column_formatters = {
        GrammarRule.chapter: lambda m, a: m.chapter.title if m.chapter else "",
    }

    column_searchable_list = [GrammarRule.rule_name]
    can_create = True
    can_edit = True
    can_delete = True


class KnowledgeComponentAdmin(ModelView, model=KnowledgeComponent):
    """Vue d'administration pour les composants de connaissance."""
    icon = "fa-solid fa-puzzle-piece"
    name = "Composant"
    name_plural = "Composants"
    
    # --- C'EST ICI QUE L'ON FAIT LA MODIFICATION ---
    # On remplace 'category' par les nouveaux champs de la taxonomie
    column_list = [
        KnowledgeComponent.id,
        KnowledgeComponent.title,
        KnowledgeComponent.domain,  # <-- AJOUT
        KnowledgeComponent.area,    # <-- AJOUT
        KnowledgeComponent.skill,   # <-- AJOUT
        KnowledgeComponent.component_type,
        KnowledgeComponent.chapter,
    ]
    # -----------------------------------------------

    column_searchable_list = [KnowledgeComponent.title]
    column_sortable_list = [KnowledgeComponent.id, KnowledgeComponent.title, KnowledgeComponent.component_type]
    
    column_formatters = {
        KnowledgeComponent.chapter: lambda m, a: m.chapter.title if m.chapter else "",
    }



class KnowledgeNodeAdmin(ModelView, model=KnowledgeNode):
    """Admin view for knowledge graph nodes."""

    name = "Noeud"
    name_plural = "Noeuds"
    icon = "fa-solid fa-circle-nodes"
    column_list = [
        KnowledgeNode.id,
        KnowledgeNode.title,
        KnowledgeNode.node_type,
        KnowledgeNode.course,
    ]

    column_formatters = {
        KnowledgeNode.course: lambda m, a: m.course.title if m.course else "",
    }

    column_searchable_list = [KnowledgeNode.title]
    can_create = True
    can_edit = True
    can_delete = True


class NodeExerciseAdmin(ModelView, model=NodeExercise):
    """Admin view for exercises attached to knowledge nodes."""

    name = "Exercice"
    name_plural = "Exercices"
    icon = "fa-solid fa-puzzle-piece"
    column_list = [
        NodeExercise.id,
        NodeExercise.title,
        NodeExercise.component_type,
        NodeExercise.node,
    ]

    column_formatters = {
        NodeExercise.node: lambda m, a: m.node.title if m.node else "",
    }

    column_searchable_list = [NodeExercise.title]
    can_create = True
    can_edit = True
    can_delete = True


class KnowledgeEdgeAdmin(ModelView, model=KnowledgeEdge):
    """Admin view for edges between knowledge nodes."""

    name = "Lien"
    name_plural = "Liens"
    icon = "fa-solid fa-link"
    column_list = [
        KnowledgeEdge.id,
        KnowledgeEdge.source_node,
        KnowledgeEdge.relation_type,
        KnowledgeEdge.target_node,
    ]

    column_formatters = {
        KnowledgeEdge.source_node: lambda m, a: m.source_node.title if m.source_node else "",
        KnowledgeEdge.target_node: lambda m, a: m.target_node.title if m.target_node else "",
    }

    column_searchable_list = [KnowledgeEdge.relation_type]
    can_create = True
    can_edit = True
    can_delete = True


class UserCourseProgressAdmin(ModelView, model=UserCourseProgress):
    """Admin view for user course progress."""

    name = "Progression de Cours"
    name_plural = "Progressions de Cours"
    icon = "fa-solid fa-chart-line"
    column_list = [
        UserCourseProgress.user,
        UserCourseProgress.course,
        UserCourseProgress.status,
        UserCourseProgress.current_level_order,
        UserCourseProgress.current_chapter_order,
        UserCourseProgress.last_geshtu_notification_at,
    ]

    column_formatters = {
        UserCourseProgress.user: lambda m, a: m.user.username if m.user else "",
        UserCourseProgress.course: lambda m, a: m.course.title if m.course else "",
    }

    column_searchable_list = [UserCourseProgress.status]
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

    excluded = {
        User,
        Course,
        AITokenLog,
        ContentFeedback,
        Level,
        Chapter,
        VocabularyItem,
        GrammarRule,
        KnowledgeComponent,
        KnowledgeNode,
        NodeExercise,
        KnowledgeEdge,
        UserCourseProgress,
    }

    meta = type(ModelView)
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if model in excluded:
            continue
        view = meta(f"{model.__name__}Admin", (ModelView,), {}, model=model)
        admin.add_view(view)

