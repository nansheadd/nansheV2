# Fichier : backend/app/db/base.py (Version Corrigée et Complète)

# --- Import de la classe de base ---
from app.db.base_class import Base

# --- ORDRE D'IMPORTATION STRICT POUR ÉVITER LES DÉPENDANCES CIRCULAIRES ---

# 1. Modèles fondamentaux ("Parents")
from app.models.user.user_model import User
from app.models.course.course_model import Course

# 2. Modèles directement liés à User et Course
from app.models.course.level_model import Level
from app.models.course.character_model import Character, CharacterSet
from app.models.progress.user_course_progress_model import UserCourseProgress

# 3. Modèles de contenu, qui dépendent des modèles ci-dessus
from app.models.course.chapter_model import Chapter
from app.models.course.vocabulary_item_model import VocabularyItem
from app.models.course.grammar_rule_model import GrammarRule
from app.models.course.knowledge_component_model import KnowledgeComponent

# 4. Nouveaux modèles de graphe de connaissances
from app.models.course.knowledge_graph_model import KnowledgeNode, KnowledgeEdge, NodeExercise

# 5. Modèles de suivi et d'analyse (souvent les plus "enfants")
from app.models.progress.user_knowledge_strength_model import UserKnowledgeStrength
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.progress.user_topic_performance_model import UserTopicPerformance
from app.models.analytics.golden_examples_model import GoldenExample
from app.models.analytics.feedback_model import ContentFeedback
from app.models.analytics.training_example_model import TrainingExample