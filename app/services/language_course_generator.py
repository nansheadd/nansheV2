# Fichier : nanshe/backend/app/services/language_course_generator.py (VERSION REFACTORISÉE)

import logging
import json
from sqlalchemy.orm import Session

# On utilise les nouveaux chemins d'importation
from app.models.user.user_model import User
from app.models.course import (
    course_model, level_model, chapter_model, character_model
)
from app.models.progress import user_course_progress_model
from app.core import ai_service, prompt_manager # <-- IMPORT DU PROMPT_MANAGER
from app.schemas.course import course_schema
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LanguageCourseGenerator:
    """
    Orchestre la création de l'échafaudage complet et structuré d'un cours de langue.
    """
    def __init__(self, db: Session, db_course: course_model.Course, creator: User):
        self.db = db
        self.db_course = db_course  # On reçoit le cours existant
        self.course_in = course_schema.CourseCreate(title=db_course.title, model_choice=db_course.model_choice)
        self.model_choice = db_course.model_choice
        self.creator = creator

    def generate_full_course_scaffold(self):
        """
        Méthode principale qui génère l'ÉCHAFAUDAGE du cours.
        """
        try:
            logger.info(f"Génération de l'échafaudage pour le cours de langue '{self.db_course.title}' (ID: {self.db_course.id})")
            
            # On ne crée plus d'entrée, on la met à jour
            self.db_course.generation_status = "generating"
            self.db.commit()

            # Les étapes de génération restent les mêmes
            course_plan = self._generate_full_course_plan()
            self._apply_full_course_plan(course_plan)
            
            character_sets = self._generate_character_sets()
            self._save_character_sets(character_sets)

            # Finalisation
            self.db_course.generation_status = "completed"
            self.db.commit()
            
            self._enroll_creator()
            self.db.commit()

            logger.info(f"Échafaudage généré et créateur inscrit pour le cours ID {self.db_course.id}")
            return self.db_course

        except Exception as e:
            logger.error(f"Erreur majeure lors de la génération de l'échafaudage : {e}", exc_info=True)
            if self.db_course:
                self.db.rollback()
                self.db_course.generation_status = "failed"
                self.db.commit()
            return None
    
    # --- MÉTHODES PRIVÉES DE LA PIPELINE ---

    def _create_initial_course_entry(self):
        """Crée l'enregistrement de base pour le cours."""
        logger.info("  Étape 1: Création de l'entrée en base de données.")
        self.db_course = course_model.Course(
            title=self.course_in.title,
            model_choice=self.model_choice,
            generation_status="generating",
            course_type="langue"
        )
        self.db.add(self.db_course)
        self.db.commit()
        self.db.refresh(self.db_course)

    def _generate_full_course_plan(self) -> Dict[str, Any]:
        """Appelle l'IA pour générer le plan complet du cours via le prompt manager."""
        logger.info("  Étape 2: Génération du plan de cours complet par l'IA.")
        
        system_prompt = prompt_manager.get_prompt("language_generation.full_course_plan")
        user_prompt = f"Langue à apprendre : {self.course_in.title}"
        
        response_str = ai_service._call_ai_model(user_prompt, self.model_choice, system_prompt=system_prompt)
        return json.loads(response_str)

    def _apply_full_course_plan(self, plan: Dict[str, Any]):
        """Sauvegarde le plan de cours (niveaux et chapitres) en BDD."""
        if not plan: raise ValueError("Le plan de cours généré est vide.")
        
        self.db_course.description = plan.get("overview", f"Un cours fascinant sur {self.db_course.title}")
        
        for i, level_data in enumerate(plan.get("levels", [])):
            db_level = level_model.Level(
                course_id=self.db_course.id,
                title=level_data.get("level_title", f"Niveau {i+1}"),
                level_order=i,
                are_chapters_generated=True
            )
            self.db.add(db_level)
            self.db.flush() 

            for j, chapter_title in enumerate(level_data.get("chapters", [])):
                db_chapter = chapter_model.Chapter(
                    level_id=db_level.id,
                    title=chapter_title,
                    chapter_order=j,
                    lesson_status="pending",
                    exercises_status="pending"
                )
                self.db.add(db_chapter)

    def _generate_character_sets(self) -> Dict[str, Any]:
        """Appelle l'IA pour générer les alphabets/syllabaires via le prompt manager."""
        logger.info("  Étape 3: Génération des jeux de caractères par l'IA.")
        
        system_prompt = prompt_manager.get_prompt("language_generation.character_sets")
        user_prompt = f"Langue : {self.course_in.title}"

        response_str = ai_service._call_ai_model(user_prompt, self.model_choice, system_prompt=system_prompt)
        return json.loads(response_str)

    def _save_character_sets(self, data: Dict[str, Any]):
        """Sauvegarde les jeux de caractères en BDD."""
        for set_data in data.get("character_sets", []):
            db_set = character_model.CharacterSet(
                course_id=self.db_course.id,
                name=set_data.get("name")
            )
            self.db.add(db_set)
            self.db.flush()

            for char_data in set_data.get("characters", []):
                db_char = character_model.Character(
                    character_set_id=db_set.id,
                    symbol=char_data.get("symbol"),
                    pronunciation=char_data.get("pronunciation")
                )
                self.db.add(db_char)

    def _enroll_creator(self):
        """Inscrit le créateur au cours."""
        logger.info("  Étape finale: Inscription du créateur au cours.")
        progress = user_course_progress_model.UserCourseProgress(
            user_id=self.creator.id, 
            course_id=self.db_course.id, 
            current_level_order=0,
            current_chapter_order=0
        )
        self.db.add(progress)