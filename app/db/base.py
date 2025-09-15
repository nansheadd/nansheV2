# Fichier: app/db/base.py

# --- Import de la classe de base ---
# Cet import garantit que tous les modèles qui en héritent seront correctement enregistrés.
from app.db.base_class import Base

# --- ORDRE D'IMPORTATION STRATÉGIQUE POUR LA DÉCOUVERTE DES MODÈLES ---

# 1. Modèles principaux et indépendants
from app.models.user.user_model import User
from app.models.course.course_model import Course
from app.models.user.notification_model import Notification
from app.models.user.badge_model import Badge, UserBadge

# 2. Modèles de la nouvelle architecture "Capsule"
# On importe chaque entité depuis son propre fichier.
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.atom_model import Atom
from app.models.capsule.language_roadmap_model import LanguageRoadmapLevel
from app.models.capsule.utility_models import (
    UserCapsuleEnrollment, 
    UserCapsuleProgress
)

# On importe tous les nouveaux modèles de roadmap depuis leur fichier unique
from app.models.capsule.language_roadmap_model import (
    LanguageRoadmapLevel,
    Skill,
    LevelSkillTarget,
    LevelFocus,
    LevelCheckpoint,
    LevelReward
)

# 3. Anciens modèles de cours (si toujours utilisés)
from app.models.course.level_model import Level
from app.models.course.chapter_model import Chapter
from app.models.course.character_model import Character, CharacterSet
from app.models.course.vocabulary_item_model import VocabularyItem
from app.models.course.grammar_rule_model import GrammarRule
from app.models.course.knowledge_component_model import KnowledgeComponent

# 4. Modèles de Graphe de Connaissances
from app.models.course.knowledge_graph_model import KnowledgeNode, KnowledgeEdge, NodeExercise

# 5. Modèles de suivi de progression
from app.models.progress.user_course_progress_model import UserCourseProgress
from app.models.progress.user_knowledge_strength_model import UserKnowledgeStrength
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.progress.user_activity_log_model import UserActivityLog
from app.models.progress.user_topic_performance_model import UserTopicPerformance
from app.models.progress.user_character_strength_model import UserCharacterStrength
from app.models.progress.user_vocabulary_strenght_model import UserVocabularyStrength

# 6. Modèles d'analyse et de données vectorielles
from app.models.analytics.golden_examples_model import GoldenExample
from app.models.analytics.feedback_model import ContentFeedback
from app.models.analytics.vector_store_model import VectorStore

# NOTE: En important tous les modèles ici, vous vous assurez que les outils
# de migration comme Alembic ou la création initiale de la base de données
# connaissent l'intégralité de votre schéma.