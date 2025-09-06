# Fichier: backend/app/services/course_generator.py (CORRIGÉ)

import logging
import json
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.models.analytics.vector_store_model import VectorStore
from app.services.classification_service import db_classifier
from app.models.user import user_model
from app.models.course import chapter_model, course_model, level_model, knowledge_component_model
from app.models.progress import user_course_progress_model
from app.schemas.course import course_schema
from app.core import ai_service

logger = logging.getLogger(__name__)

class CourseGenerator:
    def __init__(self, db: Session, course_in: course_schema.CourseCreate, creator: user_model.User):
        self.db = db
        self.course_in = course_in
        self.model_choice = course_in.model_choice
        self.creator = creator
        self.db_course: course_model.Course = None

    def initialize_course_and_start_generation(self, background_tasks: BackgroundTasks) -> course_model.Course:
        """
        NOUVELLE MÉTHODE : Classifie, crée l'entrée initiale en BDD de manière synchrone,
        puis ajoute la génération complète à la file d'attente des tâches de fond.
        """
        # Étape 1: Classifier le sujet AVANT de toucher à la BDD
        classification = db_classifier.classify(self.course_in.title, self.db, top_k=1)
        if not classification:
            raise HTTPException(status_code=400, detail=f"Impossible de classifier le sujet '{self.course_in.title}'.")
        
        category = classification[0]['category']
        
        # Étape 2: Créer l'entrée en BDD avec toutes les infos nécessaires
        self._create_initial_course_entry(category)

        # Étape 3: Ajouter la tâche de fond pour la génération du contenu
        background_tasks.add_task(self.generate_full_course_intelligently, classification)
        
        # Étape 4: Retourner l'objet cours initial à l'API pour la réponse 202
        return self.db_course

    def generate_full_course_intelligently(self, classification: list):
        """
        Méthode principale de génération (exécutée en arrière-plan).
        """
        try:
            category = classification[0]['category']
            logger.info(f"GÉNÉRATION (BG) : Démarrage pour '{self.db_course.title}' (ID: {self.db_course.id})")

            # Chercher un plan de cours EXACTEMENT correspondant
            exact_plan = self.db.query(VectorStore).filter(
                VectorStore.content_type == 'course_plan',
                VectorStore.skill == self.course_in.title
            ).first()

            course_plan_text = None
            if exact_plan:
                logger.info(f"  -> ✅ Plan de cours trouvé directement pour '{self.course_in.title}'.")
                course_plan_text = exact_plan.chunk_text
            else:
                logger.info(f"  -> Aucun plan exact. Recherche d'un modèle similaire...")
                analog_plan_entry = self.db.query(VectorStore).filter(
                    VectorStore.content_type == 'course_plan',
                    VectorStore.domain == category['domain'],
                    VectorStore.area == category['area']
                ).order_by(
                    VectorStore.embedding.cosine_distance(classification[0]['embedding'])
                ).first()

                if analog_plan_entry:
                    logger.info(f"  -> 🤖 Modèle trouvé : '{analog_plan_entry.skill}'. Génération RAG...")
                    prompt = self._build_rag_prompt(self.course_in.title, analog_plan_entry)
                    new_plan_text = ai_service.generate_text(prompt, self.model_choice)
                    self._save_new_plan_to_vector_store(new_plan_text, category)
                    course_plan_text = new_plan_text
                else:
                    logger.warning(f"  -> ⚠️ Aucun modèle. Génération à froid...")
                    plan_json = self._generate_course_plan()
                    course_plan_text = json.dumps(plan_json, indent=2, ensure_ascii=False)

            if course_plan_text:
                self.generate_final_course_from_plan(course_plan_text)
            else:
                raise ValueError("Aucun plan de cours n'a pu être obtenu.")

        except Exception as e:
            logger.error(f"GÉNÉRATION (BG) : Erreur majeure pour le cours ID {self.db_course.id}. Exception: {e}", exc_info=True)
            self.db_course.generation_status = "failed"
            self.db.commit()

    def _create_initial_course_entry(self, category: Dict[str, str]):
        """Crée l'enregistrement de base pour le cours avec le type déjà défini."""
        logger.info(f"  -> Création de l'entrée en BDD avec le type '{category.get('domain', 'unknown')}'.")
        db_course = course_model.Course(
            title=self.course_in.title,
            model_choice=self.model_choice,
            generation_status="generating",
            domain=category.get('domain'),
            area=category.get('area'),
            course_type=category.get('domain', 'unknown') 
        )
        self.db.add(db_course)
        self.db.commit()
        self.db.refresh(db_course)
        self.db_course = db_course
        
    def generate_final_course_from_plan(self, course_plan_text: str):
        """Prend un plan TEXTE et construit le cours."""
        try:
            logger.info(f"GÉNÉRATION FINALE : Application du plan pour le cours '{self.db_course.title}'")
            learning_plan_json = json.loads(course_plan_text)
            self._apply_learning_plan(learning_plan_json)
            
            for level in self.db_course.levels:
                self._generate_chapters_for_level(level)

            for level in self.db_course.levels:
                for chapter in level.chapters:
                    self._generate_lesson_for_chapter(chapter)
                    if chapter.lesson_status == "completed":
                        self._generate_exercises_for_lesson(chapter)
            
            self.db_course.generation_status = "completed"
            self._enroll_creator()
            self.db.commit()
            logger.info(f"GÉNÉRATION FINALE : Succès pour le cours ID {self.db_course.id}")
            return self.db_course
        except Exception as e:
            logger.error(f"GÉNÉRATION FINALE : Erreur pour le cours '{self.db_course.title}'. Exception: {e}", exc_info=True)
            if self.db_course:
                self.db_course.generation_status = "failed"
                self.db.commit()
            return None
    
    def _build_rag_prompt(self, title: str, analog_plan: VectorStore) -> str:
        return f"""
        Tu es un concepteur pédagogique expert.
        Ta mission est de créer un plan de cours détaillé et structuré en JSON pour le sujet : "{title}".
        Inspire-toi FORTEMENT de l'exemple de plan de cours suivant, qui traite d'un sujet de la même catégorie :
        --- EXEMPLE DE PLAN DE COURS POUR "{analog_plan.skill}" ---
        {analog_plan.chunk_text}
        --- FIN DE L'EXEMPLE ---
        Maintenant, en gardant une structure JSON et un niveau de détail similaires, génère le plan de cours complet pour "{title}".
        La sortie doit être un objet JSON valide contenant une clé "overview" (string) et une clé "levels" (liste d'objets, chacun avec "level_title" et "chapters").
        """

    def _save_new_plan_to_vector_store(self, plan_text: str, category: Dict[str, str]):
        logger.info(f"  -> Sauvegarde du nouveau plan pour '{self.course_in.title}' dans la base vectorielle.")
        embedding = db_classifier.model.encode(plan_text)
        new_plan_entry = VectorStore(
            chunk_text=plan_text, embedding=embedding, domain=category['domain'],
            area=category['area'], skill=self.course_in.title, content_type='course_plan'
        )
        self.db.add(new_plan_entry)
        self.db.commit()

    def _generate_course_plan(self) -> Dict[str, Any]:
        logger.info("  -> Génération d'un plan de cours de base (sans RAG).")
        return ai_service.generate_learning_plan(
            title=self.db_course.title,
            course_type=f"{self.db_course.domain}/{self.db_course.area}",
            model_choice=self.model_choice
        )

    def _apply_learning_plan(self, plan: Dict[str, Any]):
        if not plan: raise ValueError("Le plan de cours généré est vide.")
        self.db_course.description = plan.get("overview", f"Un cours sur {self.db_course.title}")
        self.db_course.learning_plan_json = plan
        levels_data = plan.get("levels", [])
        if not levels_data: raise ValueError("Le plan de cours ne contient aucun niveau.")
        for i, level_data in enumerate(levels_data):
            db_level = level_model.Level(
                course_id=self.db_course.id,
                title=level_data.get("level_title", f"Niveau {i+1}"),
                level_order=i
            )
            self.db.add(db_level)
        self.db.commit()
        self.db.refresh(self.db_course)

    def _generate_chapters_for_level(self, level: level_model.Level):
        logger.info(f"  Génération des chapitres pour '{level.title}'.")
        chapters_data = self.db_course.learning_plan_json.get("levels", [])[level.level_order].get("chapters", [])
        if not chapters_data: return
        for i, chap_data in enumerate(chapters_data):
            chapter = chapter_model.Chapter(level_id=level.id, title=chap_data.get("chapter_title"), chapter_order=i)
            self.db.add(chapter)
        level.are_chapters_generated = True
        self.db.commit()

    def _generate_lesson_for_chapter(self, chapter: chapter_model.Chapter):
        logger.info(f"    Génération de la leçon pour '{chapter.title}'.")
        # ... (le reste est inchangé)

    def _generate_exercises_for_lesson(self, chapter: chapter_model.Chapter):
        logger.info(f"    Génération des exercices pour '{chapter.title}'.")
        # ... (le reste est inchangé)

    def _enroll_creator(self):
        logger.info("  Inscription du créateur au cours.")
        # ... (le reste est inchangé)