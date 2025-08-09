# Fichier: backend/app/db/base.py (VERSION FINALE ET CORRECTEMENT ORDONNÉE)

# Ce fichier est le point de rencontre de tous les modèles.
# L'importer garantit que SQLAlchemy découvre les tables dans le bon ordre
# avant d'essayer de construire les relations entre elles.

from app.db.base_class import Base

# --- ORDRE D'IMPORTATION STRICT ---

# 1. Modèles "Parents" qui n'ont pas de dépendances étrangères vers d'autres tables.
#    Ceux-ci doivent être connus en premier.
from app.models.user_model import User
from app.models.course_model import Course

# 2. Modèles qui dépendent de User et Course.
from app.models.level_model import Level # Dépend de `Course`
from app.models.user_course_progress_model import UserCourseProgress # Dépend de `User` et `Course`

# 3. Modèles qui représentent la structure du contenu.
from app.models.chapter_model import Chapter # Dépend de `Level`
from app.models.knowledge_component_model import KnowledgeComponent # Dépend de `Chapter`

# 4. Modèles "Enfants" finaux qui lient les utilisateurs aux plus petits éléments.
#    C'est l'étape cruciale pour corriger votre erreur.
#    Ces modèles ne peuvent être importés qu'APRÈS que `User` et `KnowledgeComponent` soient connus.
from app.models.user_knowledge_strength_model import UserKnowledgeStrength # Dépend de `User` et `KnowledgeComponent`
from app.models.user_answer_log_model import UserAnswerLog # Dépend de `User` et `KnowledgeComponent`
from app.models.user_topic_performance_model import UserTopicPerformance