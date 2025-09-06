# Fichier: nanshe/backend/app/services/language_course_generator.py (VERSION FINALE OPTIMISÉE)
import logging
import time
from sqlalchemy.orm import Session
from typing import Tuple, Optional, Dict, Any, List

from app.models.user.user_model import User
from app.models.course import (
    course_model, level_model, chapter_model, character_model
)
from app.models.progress import user_course_progress_model
from app.core import ai_service, prompt_manager
from .rag_utils import _find_similar_examples

logger = logging.getLogger(__name__)

def _update_progress(db: Session, course: course_model.Course, step: str, progress: int):
    db_course = db.get(course_model.Course, course.id)
    if db_course:
        db_course.generation_step = step
        db_course.generation_progress = progress
        db.commit()
        logger.info(f"  -> Progress Update (Course ID {course.id}): {progress}% - {step}")
        time.sleep(0.2) # Petite pause pour la visibilité du frontend
    else:
        logger.error(f"  -> FAILED Progress Update (Course ID {course.id}): Course not found.")

def _split_title_and_meta(chapter_entry: Any, fallback_title: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    if isinstance(chapter_entry, dict):
        title = chapter_entry.get("title") or chapter_entry.get("chapter_title") or fallback_title
        meta = {k: v for k, v in chapter_entry.items() if k not in ("title", "chapter_title", "is_theoretical")}
        is_theoretical = chapter_entry.get("is_theoretical", False)
        return str(title), is_theoretical, meta
    return str(chapter_entry), False, None

def _level_meta(level_data: Dict[str, Any]) -> Dict[str, Any]:
    exclude = {"level_title", "chapters"}
    return {k: v for k, v in level_data.items() if k not in exclude}

class LanguageCourseGenerator:
    def __init__(self, db: Session, db_course: course_model.Course, creator: User):
        self.db = db
        self.db_course = db_course
        self.creator = creator
        self.language = db_course.title.replace("apprendre le ", "").replace("le ", "").strip().lower()

    def generate_full_course_scaffold(self):
        """
        Orchestre la création complète du cours en un seul appel IA pour une vitesse maximale.
        """
        try:
            logger.info(f"Génération optimisée de l'échafaudage pour '{self.db_course.title}' avec RAG.")
            self.db_course.generation_status = "generating"
            _update_progress(self.db, self.db_course, "Initialisation...", 5)

            # --- ÉTAPE 1: UN SEUL APPEL IA POUR TOUTE LA STRUCTURE ---
            _update_progress(self.db, self.db_course, "Conception du plan de cours complet...", 15)
            full_scaffold = self._generate_full_scaffold_rag()

            # --- ÉTAPE 2: PARSE ET SAUVEGARDE EN BDD ---
            _update_progress(self.db, self.db_course, "Sauvegarde du plan et des alphabets...", 60)
            self._apply_full_scaffold(full_scaffold)

            _update_progress(self.db, self.db_course, "Finalisation...", 95)
            self.db_course.generation_status = "completed"
            self.db_course.generation_progress = 100
            self.db.commit()
            
            self._enroll_creator()
            self.db.commit()

            logger.info(f"Échafaudage RAG optimisé généré pour le cours ID {self.db_course.id}")
            return self.db_course

        except Exception as e:
            logger.error(f"Erreur majeure lors de la génération de l'échafaudage : {e}", exc_info=True)
            if self.db_course:
                self.db.rollback()
                self.db_course.generation_status = "failed"
                self.db_course.generation_step = "Une erreur est survenue"
                self.db.commit()
            return None

    def _generate_full_scaffold_rag(self) -> Dict[str, Any]:
        """
        Effectue un unique appel à l'IA pour générer le plan de cours ET les alphabets.
        """
        logger.info("  -> Recherche d'exemples complets de cours...")
        rag_context = _find_similar_examples(self.db, self.db_course.title, self.language, "course_plan_structure", limit=3)
        rag_context += _find_similar_examples(self.db, f"Système d'écriture {self.language}", self.language, "character_set_structure", limit=2)

        system_prompt = prompt_manager.get_prompt(
            "language_generation.full_course_scaffold", # Un nouveau prompt plus complet
            course_title=self.db_course.title,
            max_level=self.db_course.max_level,
            rag_context=rag_context,
            ensure_json=True
        )
        user_prompt = f"Génère la structure complète du cours pour {self.db_course.title}, incluant le plan et les alphabets de base."
        scaffold = ai_service._call_ai_model_json(user_prompt, self.db_course.model_choice, system_prompt=system_prompt)
        return scaffold or {}

    def _apply_full_scaffold(self, scaffold: Dict[str, Any]):
        """
        Parse la réponse complète de l'IA et sauvegarde tout en BDD.
        """
        if not scaffold:
            raise ValueError("L'échafaudage de cours généré est vide.")

        # Sauvegarde du plan (niveaux et chapitres)
        logger.info("  -> Application du plan de cours...")
        levels = scaffold.get("levels", [])
        for i, level_data in enumerate(levels):
            db_level = level_model.Level(
                course_id=self.db_course.id,
                title=level_data.get("level_title", f"Niveau {i+1}"),
                level_order=i,
                are_chapters_generated=True
            )
            self.db.add(db_level)
            self.db.flush()

            for j, ch_data in enumerate(level_data.get("chapters", [])):
                title, is_theoretical, _ = _split_title_and_meta(ch_data, f"Chapitre {j+1}")
                db_chapter = chapter_model.Chapter(
                    level_id=db_level.id,
                    title=title,
                    chapter_order=j,
                    is_theoretical=is_theoretical,
                    lesson_status="pending",
                    exercises_status="pending"
                )
                self.db.add(db_chapter)
        
        # Sauvegarde des alphabets
        logger.info("  -> Sauvegarde des alphabets...")
        character_sets = scaffold.get("character_sets", [])
        for set_data in character_sets:
            if not isinstance(set_data, dict) or not set_data.get("name"):
                continue
            
            db_set = character_model.CharacterSet(
                course_id=self.db_course.id,
                name=set_data.get("name"),
                description=set_data.get("description")
            )
            self.db.add(db_set)
        
        self.db.commit()

    def _enroll_creator(self):
        logger.info("  Étape finale: Inscription du créateur au cours.")
        progress = user_course_progress_model.UserCourseProgress(
            user_id=self.creator.id, 
            course_id=self.db_course.id, 
            current_level_order=0,
            current_chapter_order=0
        )
        self.db.add(progress)