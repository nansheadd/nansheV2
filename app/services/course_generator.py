import logging
import json
import pickle
from pathlib import Path
from typing import Dict, Any

import numpy as np
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from app.core import ai_service
from app.models.course import (chapter_model, course_model,
                               knowledge_graph_model, level_model)
from app.models.progress import user_course_progress_model
from app.models.user import user_model
from app.schemas.course import course_schema

logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURATION DU CLASSIFIEUR NLP
# ==============================================================================

# On charge le modèle de base une seule fois au démarrage pour de meilleures performances.
try:
    nlp_model = SentenceTransformer('all-MiniLM-L6-v2')
    logger.info("✅ Modèle NLP de base (SentenceTransformer) chargé.")
except Exception as e:
    nlp_model = None
    logger.error(f"❌ Échec critique du chargement du modèle NLP de base : {e}")

# Chemin vers notre classifieur entraîné. Il sera chargé à la demande.
CLASSIFIER_PATH = Path(__file__).parent / "classifier_model.pkl"

# Données pour la méthode de secours (si le classifieur entraîné n'existe pas)
COURSE_CATEGORIES_FALLBACK = {
    "programming": {
        "description": "Apprendre à écrire du code, les algorithmes et le développement de logiciels.",
        "keywords": ["python", "javascript", "react", "java", "c++", "sql", "programmation", "développement", "coder"]
    },
    "philosophy": {
        "description": "Étude des questions fondamentales sur l'existence, la connaissance et les valeurs.",
        "keywords": ["philosophie", "philo", "stoïcisme", "platon", "kant", "nietzsche", "métaphysique"]
    },
    "language": {
        "description": "Apprentissage d'une nouvelle langue étrangère.",
        "keywords": ["anglais", "japonais", "espagnol", "allemand", "apprendre une langue"]
    }
}
# Pré-calcul des vecteurs pour la méthode de secours
fallback_vectors = {}
if nlp_model:
    for name, data in COURSE_CATEGORIES_FALLBACK.items():
        all_texts = [data["description"]] + data["keywords"]
        fallback_vectors[name] = nlp_model.encode(all_texts)

# ==============================================================================

class CourseGenerator:
    """
    Contient la logique de classification de cours et le pipeline de génération
    pour les cours de type "générique".
    """
    def __init__(self, db: Session, course_in: course_schema.CourseCreate, creator: user_model.User):
        self.db = db
        self.course_in = course_in
        self.model_choice = course_in.model_choice
        self.creator = creator
        self.db_course: course_model.Course = None
        self.course_type = "generic"
        self.trained_classifier = None

    def _load_trained_classifier(self):
        """Tente de charger le classifieur depuis le fichier .pkl et le met en cache."""
        if hasattr(self, '_classifier_loaded'):
            return

        if CLASSIFIER_PATH.exists():
            try:
                with open(CLASSIFIER_PATH, 'rb') as f:
                    self.trained_classifier = pickle.load(f)
                logger.info(f"✅ Classifieur entraîné chargé avec succès depuis '{CLASSIFIER_PATH}'.")
            except Exception as e:
                logger.error(f"❌ Erreur lors du chargement du classifieur entraîné: {e}")
        else:
            logger.warning(f"ℹ️ Fichier classifieur non trouvé à '{CLASSIFIER_PATH}'. Utilisation du mode fallback.")
        
        self._classifier_loaded = True

    def _determine_course_type(self, title: str) -> str:
        """Détermine le type de cours en donnant la priorité absolue au classifieur entraîné."""
        if not nlp_model or not title:
            return "generic"

        self._load_trained_classifier()
        title_vector = nlp_model.encode([title])
        
        if self.trained_classifier:
            try:
                prediction_index = self.trained_classifier['classifier'].predict(title_vector)[0]
                category = self.trained_classifier['encoder'].inverse_transform([prediction_index])[0]
                logger.info(f"🤖 Prédiction du classifieur ENTRAÎNÉ pour '{title}': '{category}'")
                return category
            except Exception as e:
                logger.error(f"⚠️ Échec de la prédiction avec le modèle entraîné ({e}), passage au fallback.")

        logger.info(f"🔍 Utilisation du classifieur par similarité sémantique (fallback) pour '{title}'.")
        best_match = "generic"
        highest_similarity = 0.6
        for name, vectors in fallback_vectors.items():
            similarities = cosine_similarity(title_vector, vectors)[0]
            max_sim_for_category = np.max(similarities)
            if max_sim_for_category > highest_similarity:
                highest_similarity = max_sim_for_category
                best_match = name
        
        logger.info(f"➡️ Résultat du fallback pour '{title}': '{best_match}' (similarité: {highest_similarity:.2f})")
        return best_match

    def generate_full_course(self):
        """Pipeline de génération complet pour un cours de type GÉNÉRIQUE."""
        try:
            logger.info(f"GÉNÉRATION GÉNÉRIQUE : Démarrage pour le cours '{self.course_in.title}'")
            if not self.db_course: self._create_initial_course_entry()

            self.db_course.generation_status = "generating"
            self.db.commit()

            plan = self._generate_course_plan()
            self._apply_learning_plan(plan)
            
            self._generate_chapters_for_level(self.db_course.levels[0]) # Génère les chapitres du premier niveau
            self._generate_initial_content() # Génère le contenu du premier chapitre
            
            self.db_course.generation_status = "completed"
            self._enroll_creator()
            self.db.commit()
            logger.info(f"GÉNÉRATION GÉNÉRIQUE : Succès pour le cours ID {self.db_course.id}")
            return self.db_course
        except Exception as e:
            logger.error(f"GÉNÉRATION GÉNÉRIQUE : Erreur majeure pour '{self.course_in.title}'. Exception: {e}", exc_info=True)
            if self.db_course: self.db_course.generation_status = "failed"; self.db.commit()
            return None

    def _create_initial_course_entry(self):
        """Crée l'enregistrement de base pour le cours."""
        logger.info("  Étape 1: Création de l'entrée en base de données.")
        self.db_course = course_model.Course(title=self.course_in.title, model_choice=self.model_choice, generation_status="pending", course_type="unknown")
        self.db.add(self.db_course); self.db.commit(); self.db.refresh(self.db_course)

    def _generate_course_plan(self) -> Dict[str, Any]:
        """Génère la description et les niveaux du cours."""
        logger.info("  Étape 2: Génération du plan de cours (niveaux).")
        # Le type de cours a déjà été défini par la tâche de fond, on le réutilise
        return ai_service.generate_learning_plan(title=self.db_course.title, course_type=self.db_course.course_type, model_choice=self.model_choice)

    def _apply_learning_plan(self, plan: Dict[str, Any]):
        """Applique le plan généré à l'objet db_course."""
        if not plan: raise ValueError("Le plan de cours généré est vide.")
        self.db_course.description = plan.get("overview", f"Un cours sur {self.db_course.title}")
        self.db_course.learning_plan_json = plan
        for i, level_data in enumerate(plan.get("levels", [])):
            self.db.add(level_model.Level(course_id=self.db_course.id, title=level_data.get("level_title", f"Niveau {i+1}"), level_order=i))
        self.db.commit(); self.db.refresh(self.db_course)

    def _generate_chapters_for_level(self, level: level_model.Level):
        """Génère les titres des chapitres pour un niveau."""
        logger.info(f"  Étape 3: Génération des chapitres pour '{level.title}'.")
        user_context_str = json.dumps(getattr(self.course_in, 'personalization_details', {}))
        chapter_titles = ai_service.generate_chapter_plan_for_level(level_title=level.title, model_choice=self.model_choice, user_context=user_context_str)
        for i, title in enumerate(chapter_titles):
            self.db.add(chapter_model.Chapter(level_id=level.id, title=title, chapter_order=i))
        level.are_chapters_generated = True; self.db.commit()

    def _generate_initial_content(self):
        """Génère le contenu du tout premier chapitre du cours."""
        first_chapter = self.db.query(chapter_model.Chapter).join(level_model.Level).filter(level_model.Level.course_id == self.db_course.id).order_by(level_model.Level.level_order, chapter_model.Chapter.chapter_order).first()
        if not first_chapter: return

        logger.info(f"  Étape 4: Génération du contenu initial pour '{first_chapter.title}'.")
        self._generate_lesson_for_chapter(first_chapter)
        if first_chapter.lesson_status == "completed":
            self._generate_exercises_for_lesson(first_chapter)

    def _generate_lesson_for_chapter(self, chapter: chapter_model.Chapter):
        """Génère la leçon pour un chapitre."""
        lesson_text = ai_service.generate_lesson_for_chapter(chapter_title=chapter.title, model_choice=self.model_choice)
        chapter.lesson_text = lesson_text
        chapter.lesson_status = "completed" if lesson_text else "failed"
        self.db.commit()

    def _generate_exercises_for_lesson(self, chapter: chapter_model.Chapter):
        """Génère les exercices pour un chapitre générique (pas de code)."""
        exercises_data = ai_service.generate_exercises_for_lesson(db=self.db, user=self.creator, lesson_text=chapter.lesson_text, chapter_title=chapter.title, course_type=self.db_course.course_type, model_choice=self.model_choice)
        if exercises_data:
            for data in exercises_data:
                self.db.add(knowledge_graph_model.KnowledgeComponent(chapter_id=chapter.id, **data))
            chapter.exercises_status = "completed"
        else:
            chapter.exercises_status = "failed"
        self.db.commit()

    def _enroll_creator(self):
        """Inscrit le créateur au cours."""
        logger.info("  Étape 5: Inscription du créateur au cours.")
        self.db.add(user_course_progress_model.UserCourseProgress(user_id=self.creator.id, course_id=self.db_course.id, current_level_order=0))