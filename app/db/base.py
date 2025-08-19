# Fichier à modifier : nanshe/backend/app/db/base.py

from app.db.base_class import Base

# --- ORDRE D'IMPORTATION STRICT ---

# 1. Modèles "Parents"
from app.models.user.user_model import User
from app.models.course.course_model import Course

# 2. Modèles qui dépendent de User et Course
from app.models.course.level_model import Level
from app.models.progress.user_course_progress_model import UserCourseProgress
from app.models.course.character_model import Character, CharacterSet # <-- AJOUTER ICI

# 3. Modèles qui représentent la structure du contenu
from app.models.course.chapter_model import Chapter
from app.models.course.knowledge_component_model import KnowledgeComponent
from app.models.course.vocabulary_item_model import VocabularyItem # <-- AJOUTER ICI
from app.models.course.grammar_rule_model import GrammarRule     # <-- AJOUTER ICI

# 4. Modèles "Enfants" finaux
from app.models.progress.user_knowledge_strength_model import UserKnowledgeStrength
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.progress.user_topic_performance_model import UserTopicPerformance


from app.models.user.user_model import User
from app.models.progress.user_course_progress_model import UserCourseProgress
from app.models.analytics.golden_examples_model import GoldenExample
from app.models.analytics.feedback_model import FeedbackRating, FeedbackStatus