# Fichier: backend/app/admin.py (VERSION FINALE POUR SQLADMIN)
from sqladmin import ModelView
from wtforms import SelectField
from app.models.user.user_model import User
from app.models.course.course_model import Course
from app.models.analytics.ai_token_log_model import AITokenLog
from sqladmin.filters import StaticValuesFilter, ForeignKeyFilter  # ⬅️ NEW

from app.models.analytics.feedback_model import ContentFeedback, FeedbackStatus, FeedbackRating



class UserAdmin(ModelView, model=User):
    name = "Utilisateur"
    name_plural = "Utilisateurs"
    icon = "fa-solid fa-user"
    column_list = [User.id, User.username, User.email, User.is_active, User.is_superuser, User.created_at]
    column_searchable_list = [User.username, User.email]
    form_columns = [User.username, User.email, User.full_name, User.is_active, User.is_superuser]

class CourseAdmin(ModelView, model=Course):
    name = "Cours"
    name_plural = "Cours"
    icon = "fa-solid fa-book"
    column_list = [Course.id, Course.title, Course.course_type, Course.generation_status, Course.model_choice]
    column_searchable_list = [Course.title]

class AITokenLogAdmin(ModelView, model=AITokenLog):
    name = "Log de Tokens"
    name_plural = "Logs de Tokens"
    icon = "fa-solid fa-robot"
    column_list = [
        AITokenLog.id, AITokenLog.user_id, AITokenLog.timestamp, AITokenLog.feature,
        AITokenLog.model_name, AITokenLog.prompt_tokens, AITokenLog.completion_tokens, AITokenLog.cost_usd
    ]
    column_searchable_list = [AITokenLog.feature]
    can_create = False
    can_edit = False


class FeedbackAdmin(ModelView, model=ContentFeedback):
    name = "Feedback Contenu"
    name_plural = "Feedbacks Contenu"
    icon = "fa-solid fa-thumbs-up"

    # Colonnes visibles dans la liste
    column_list = [
        ContentFeedback.id,
        ContentFeedback.content_type,
        ContentFeedback.content_id,
        ContentFeedback.rating,
        ContentFeedback.status,
        ContentFeedback.user,
    ]

    column_formatters = {
        ContentFeedback.user: lambda m, a: m.user.username if m.user else ""
    }

    column_searchable_list = [ContentFeedback.content_type]

    # ✅ Filtres au format "ColumnFilter" (sinon erreur parameter_name)
    column_filters = [
        StaticValuesFilter(ContentFeedback.status, values=["pending", "approved", "rejected"], title="Statut"),
        StaticValuesFilter(ContentFeedback.rating, values=["liked", "disliked"], title="Évaluation"),
        ForeignKeyFilter(ContentFeedback.user_id, User.username, title="Utilisateur"),
    ]

    # ✅ Édition inline dans la liste (clic dans la cellule)
    column_editable_list = ["status"]   # <= important: en string

    # ✅ Édition via formulaire (page Edit)
    #    On ne montre que 'status' pour éviter les erreurs
    form_columns = ["status"]           # <= important: en string

    # ✅ Forcer un SelectField + valeurs permises
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
            "coerce": str,  # assure que la valeur postée est bien une string
        },
    }

    can_create = False   # tu gardes la création désactivée si tu veux
    can_edit = True  