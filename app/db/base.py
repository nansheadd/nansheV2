# Fichier à modifier : nanshe/backend/app/db/base.py

from app.db.base_class import Base

# --- ORDRE D'IMPORTATION STRICT ---

# 1. Modèles "Parents"
from app.models.user_model import User
from app.models.course_model import Course

# 2. Modèles qui dépendent de User et Course
from app.models.level_model import Level
from app.models.user_course_progress_model import UserCourseProgress
from app.models.character_model import Character, CharacterSet # <-- AJOUTER ICI

# 3. Modèles qui représentent la structure du contenu
from app.models.chapter_model import Chapter
from app.models.knowledge_component_model import KnowledgeComponent
from app.models.vocabulary_item_model import VocabularyItem # <-- AJOUTER ICI
from app.models.grammar_rule_model import GrammarRule     # <-- AJOUTER ICI

# 4. Modèles "Enfants" finaux
from app.models.user_knowledge_strength_model import UserKnowledgeStrength
from app.models.user_answer_log_model import UserAnswerLog
from app.models.user_topic_performance_model import UserTopicPerformance