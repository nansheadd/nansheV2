# Fichier: backend/app/services/course_generator.py
import logging
from app.models.user import user_model
from app.models.course import chapter_model
from app.models.course import course_model
from app.models.course import knowledge_component_model
from app.models.course import level_model
from sqlalchemy.orm import Session
from app.models.progress import user_course_progress_model
from app.core import ai_service
from app.schemas.course import course_schema
from typing import Dict, Any

logger = logging.getLogger(__name__)

class CourseGenerator:
    """
    Orchestre la création complète et contextuelle d'un cours,
    en maintenant le contexte de l'utilisateur à chaque étape.
    """
    def __init__(self, db: Session, course_in: course_schema.CourseCreate, creator: user_model.User):
        self.db = db
        self.course_in = course_in
        self.model_choice = course_in.model_choice
        self.creator = creator
        
        # Le cours sera créé puis enrichi
        self.db_course: course_model.Course = None

    def generate_full_course(self):
        """
        Méthode principale qui exécute le pipeline de génération complet.
        Elle est conçue pour être appelée dans une tâche de fond.
        """
        try:
            logger.info(f"GÉNÉRATION : Démarrage pour le cours '{self.course_in.title}'")
            
            # 1. Créer l'entrée "brouillon" du cours en BDD
            self._create_initial_course_entry()

            # 2. Générer le plan (description et niveaux)
            learning_plan = self._generate_course_plan()
            self._apply_learning_plan(learning_plan)
            
            # 3. Parcourir les niveaux et générer leurs chapitres
            for level in self.db_course.levels:
                self._generate_chapters_for_level(level)

            # 4. Parcourir les chapitres et générer leur contenu
            for level in self.db_course.levels:
                for chapter in level.chapters:
                    self._generate_lesson_for_chapter(chapter)
                    # La génération des exercices dépend de la leçon
                    if chapter.lesson_status == "completed":
                        self._generate_exercises_for_lesson(chapter)
            
            # 5. Finaliser
            self.db_course.generation_status = "completed"
            self._enroll_creator() # Inscrire le créateur à son propre cours
            
            self.db.commit()
            logger.info(f"GÉNÉRATION : Succès pour le cours ID {self.db_course.id}")
            return self.db_course

        except Exception as e:
            logger.error(f"GÉNÉRATION : Erreur majeure pour le cours '{self.course_in.title}'. Exception: {e}", exc_info=True)
            if self.db_course:
                self.db_course.generation_status = "failed"
                self.db.commit()
            # Il est important de ne pas propager l'exception pour ne pas faire crasher la tâche de fond
            return None

    def _create_initial_course_entry(self):
        """Crée l'enregistrement de base pour le cours et le stocke dans self.db_course."""
        logger.info("  Étape 1: Création de l'entrée en base de données.")
        db_course = course_model.Course(
            title=self.course_in.title,
            model_choice=self.model_choice,
            generation_status="generating",
            course_type="unknown" # Sera défini à la prochaine étape
        )
        self.db.add(db_course)
        self.db.commit()
        self.db.refresh(db_course)
        self.db_course = db_course

    def _generate_course_plan(self) -> Dict[str, Any]:
        """Génère la description et les niveaux du cours en utilisant le contexte complet."""
        logger.info("  Étape 2: Génération du plan de cours (niveaux).")
        
        # On utilise la fonction d'IA adaptée si les détails de personnalisation sont fournis
        if hasattr(self.course_in, 'personalization_details') and self.course_in.personalization_details:
             logger.info(f"    -> Mode adaptatif détecté avec les détails: {self.course_in.personalization_details}")
             plan = ai_service.generate_adaptive_learning_plan(
                 title=self.db_course.title,
                 course_type="unknown", # La classification se fera plus tard
                 model_choice=self.model_choice,
                 personalization_details=self.course_in.personalization_details
             )
        else:
            logger.info("    -> Mode de génération standard.")
            course_type = ai_service.classify_course_topic(title=self.db_course.title, model_choice=self.model_choice)
            self.db_course.course_type = course_type
            plan = ai_service.generate_learning_plan(
                title=self.db_course.title,
                course_type=course_type,
                model_choice=self.model_choice
            )
        return plan

    def _apply_learning_plan(self, plan: Dict[str, Any]):
        """Applique le plan généré à l'objet db_course."""
        if not plan: raise ValueError("Le plan de cours généré est vide.")
        
        self.db_course.description = plan.get("overview", f"Un cours fascinant sur {self.db_course.title}")
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
        self.db.commit() # On commit ici pour que les niveaux existent avant de créer les chapitres
        self.db.refresh(self.db_course)

    def _generate_chapters_for_level(self, level: level_model.Level):
        """Génère les chapitres pour un niveau donné en utilisant le contexte global."""
        logger.info(f"  Étape 3: Génération des chapitres pour le niveau '{level.title}'.")
        
        # Le contexte utilisateur est crucial ici
        user_context_str = f"Ce cours est destiné à un utilisateur dont les objectifs sont : {getattr(self.course_in, 'personalization_details', {})}"
        
        chapter_titles = ai_service.generate_chapter_plan_for_level(
            level_title=level.title,
            model_choice=self.model_choice,
            user_context=user_context_str,
        )
        if not chapter_titles: 
            logger.warning(f"    -> Aucun chapitre généré pour le niveau '{level.title}'.")
            return

        for i, title in enumerate(chapter_titles):
            chapter = chapter_model.Chapter(level_id=level.id, title=title, chapter_order=i)
            self.db.add(chapter)
        level.are_chapters_generated = True
        self.db.commit()

    def _generate_lesson_for_chapter(self, chapter: chapter_model.Chapter):
        """Génère le contenu de la leçon pour un chapitre."""
        logger.info(f"    Étape 4a: Génération de la leçon pour le chapitre '{chapter.title}'.")
        lesson_text = ai_service.generate_lesson_for_chapter(
            chapter_title=chapter.title,
            model_choice=self.model_choice
            # Idem, cette fonction pourrait bénéficier du contexte global.
        )
        if lesson_text:
            chapter.lesson_text = lesson_text
            chapter.lesson_status = "completed"
        else:
            chapter.lesson_status = "failed"
            logger.error(f"      -> Échec de la génération de la leçon pour '{chapter.title}'.")
        self.db.commit()

    def _generate_exercises_for_lesson(self, chapter: chapter_model.Chapter):
        """Génère les exercices pour une leçon."""
        logger.info(f"    Étape 4b: Génération des exercices pour '{chapter.title}'.")
        exercises_data = ai_service.generate_exercises_for_lesson(
            lesson_text=chapter.lesson_text,
            chapter_title=chapter.title,
            model_choice=self.model_choice
        )
        if exercises_data:
            for data in exercises_data:
                component = knowledge_component_model.KnowledgeComponent(
                    chapter_id=chapter.id,
                    title=data.get("title", "Exercice"),
                    category=data.get("category", chapter.title),
                    component_type=data.get("component_type", "unknown"),
                    bloom_level=data.get("bloom_level", "remember"),
                    content_json=data.get("content_json", {})
                )
                self.db.add(component)
            chapter.exercises_status = "completed"
        else:
            chapter.exercises_status = "failed"
            logger.error(f"      -> Échec de la génération des exercices pour '{chapter.title}'.")
        self.db.commit()

    def _enroll_creator(self):
        """Inscrit l'utilisateur créateur au cours qu'il vient de créer."""
        logger.info("  Étape 5: Inscription du créateur au cours.")
        progress = user_course_progress_model.UserCourseProgress(
            user_id=self.creator.id, 
            course_id=self.db_course.id, 
            current_level_order=0
        )
        self.db.add(progress)