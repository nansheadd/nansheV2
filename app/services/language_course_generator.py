# Fichier à créer : nanshe/backend/app/services/language_course_generator.py (NOUVEAU)

import logging
import json
from sqlalchemy.orm import Session
from app.models import (
    course_model, user_model, level_model, chapter_model,
    character_model, vocabulary_item_model, grammar_rule_model, user_course_progress_model
)
from app.core import ai_service
from app.schemas import course_schema
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LanguageCourseGenerator:
    """
    Orchestre la création complète et structurée d'un cours de langue,
    en se basant sur une véritable structure pédagogique (vocabulaire, grammaire, etc.).
    """
    def __init__(self, db: Session, course_in: course_schema.CourseCreate, creator: user_model.User):
        self.db = db
        self.course_in = course_in
        self.model_choice = course_in.model_choice
        self.creator = creator
        self.db_course: course_model.Course = None

    def generate_full_course_scaffold(self):
        """
        Méthode principale qui génère l'ÉCHAFAUDAGE complet et robuste du cours :
        le plan (niveaux, chapitres) et les jeux de caractères.
        L'inscription du créateur ne se fait qu'après la réussite complète du processus.
        """
        try:
            logger.info(f"Génération de l'échafaudage pour le cours de langue '{self.course_in.title}'")
            
            # Étape 1 : Créer l'entrée de base pour le cours avec le statut "generating"
            self._create_initial_course_entry()

            # Étape 2 : Appeler l'IA pour générer le plan de cours complet (niveaux et chapitres)
            course_plan = self._generate_full_course_plan()
            
            # Étape 3 : Sauvegarder ce plan dans la base de données
            self._apply_full_course_plan(course_plan)
            
            # Étape 4 : Appeler l'IA pour générer les jeux de caractères pour la langue
            character_sets = self._generate_character_sets()
            
            # Étape 5 : Sauvegarder ces jeux de caractères dans la base de données
            self._save_character_sets(character_sets)

            # --- CORRECTION DE LA LOGIQUE DE FINALISATION ---
            # Étape 6 : Mettre à jour le statut à "completed" et sauvegarder.
            # C'est seulement après cette étape que le cours est considéré comme viable.
            self.db_course.generation_status = "completed"
            self.db.commit()
            logger.info(f"Échafaudage généré avec succès pour le cours ID {self.db_course.id}. Procédure d'inscription...")

            # Étape 7 : Inscrire le créateur au cours maintenant qu'il est finalisé.
            # Cela évite d'avoir un cours "fantôme" dans la liste de l'utilisateur si la génération échoue.
            self._enroll_creator()
            self.db.commit()
            # --- FIN DE LA CORRECTION ---
            
            logger.info(f"Créateur inscrit avec succès pour le cours ID {self.db_course.id}")
            return self.db_course

        except Exception as e:
            logger.error(f"Erreur majeure lors de la génération de l'échafaudage : {e}", exc_info=True)
            if self.db_course:
                # En cas d'erreur à n'importe quelle étape, on s'assure que le statut est "failed"
                self.db.rollback() # Annule les changements non sauvegardés
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
            course_type="langue" # On spécifie le type
        )
        self.db.add(self.db_course)
        self.db.commit()
        self.db.refresh(self.db_course)

    def _generate_full_course_plan(self) -> Dict[str, Any]:
        """Appelle l'IA pour générer le plan complet du cours (niveaux + chapitres)."""
        logger.info("  Étape 2: Génération du plan de cours complet par l'IA.")
        system_prompt = """
        Tu es un professeur de langue expert. Conçois un programme d'apprentissage complet 
        pour un francophone débutant (niveau A1) qui veut apprendre la langue spécifiée.
        Divise ce programme en 5 à 10 niveaux logiques. Pour chaque niveau, liste 3 à 4 chapitres thématiques.
        Réponds avec un JSON ayant la structure : 
        { "overview": "...", "levels": [ { "level_title": "...", "chapters": ["..."] } ] }
        """
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
                are_chapters_generated=True # On considère le plan comme généré
            )
            self.db.add(db_level)
            self.db.flush() # Pour obtenir l'ID du niveau avant de créer les chapitres

            for j, chapter_title in enumerate(level_data.get("chapters", [])):
                db_chapter = chapter_model.Chapter(
                    level_id=db_level.id,
                    title=chapter_title,
                    chapter_order=j,
                    lesson_status="pending", # Le contenu sera généré en JIT
                    exercises_status="pending"
                )
                self.db.add(db_chapter)

    def _generate_character_sets(self) -> Dict[str, Any]:
        """Appelle l'IA pour générer les alphabets/syllabaires de la langue."""
        logger.info("  Étape 3: Génération des jeux de caractères par l'IA.")
        system_prompt = """
        Pour la langue spécifiée, liste les jeux de caractères principaux (ex: Hiragana, Katakana pour le japonais; Alphabet Cyrillique pour le russe).
        Pour chaque jeu, fournis la liste complète des caractères avec leur prononciation (romaji pour le japonais).
        Réponds avec un JSON ayant la structure :
        { "character_sets": [ { "name": "Hiragana", "characters": [ { "symbol": "あ", "pronunciation": "a" } ] } ] }
        Si la langue utilise l'alphabet latin, renvoie un tableau vide.
        """
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
        logger.info("  Étape 4: Inscription du créateur au cours.")
        progress = user_course_progress_model.UserCourseProgress(
            user_id=self.creator.id, 
            course_id=self.db_course.id, 
            current_level_order=0,
            current_chapter_order=0
        )
        self.db.add(progress)