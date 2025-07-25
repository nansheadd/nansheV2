# Fichier: nanshe/backend/app/db/base.py

# Ce fichier est le point de rencontre de tous les modèles.
# L'importer garantit que SQLAlchemy connaît toutes les tables
# avant d'essayer de construire les relations.

from app.db.base_class import Base
from app.models.user_model import User
from app.models.level_model import Level
from app.models.course_model import Course
from app.models.knowledge_component_model import KnowledgeComponent
from app.models.user_knowledge_strength_model import UserKnowledgeStrength
from app.models.user_course_progress_model import UserCourseProgress
from app.models.user_answer_log_model import UserAnswerLog