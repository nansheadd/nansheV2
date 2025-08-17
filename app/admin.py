# Fichier: backend/app/admin.py (VERSION FINALE POUR SQLADMIN)
from sqladmin import ModelView
from app.models.user.user_model import User
from app.models.course.course_model import Course
from app.models.analytics.ai_token_log_model import AITokenLog

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