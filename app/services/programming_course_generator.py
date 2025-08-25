# Fichier: backend/app/services/programming_course_generator.py (VERSION CORRIGÉE)
import logging
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
import asyncio

from app.models.course import course_model, level_model, chapter_model, knowledge_graph_model, knowledge_component_model
from app.models.user import user_model
from app.core import ai_service
from app.utils.json_utils import safe_json_loads
from app.crud.course import course_crud
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# --- TÂCHE DE FOND (Fonction globale pour la stabilité) ---
def generate_chapter_content_task(chapter_id: int, model_choice: str):
    """
    Tâche de fond autonome pour générer le contenu d'un chapitre de programmation.
    """
    db = SessionLocal()
    try:
        chapter = db.query(chapter_model.Chapter).filter(chapter_model.Chapter.id == chapter_id).first()
        if not chapter:
            logger.error(f"Tâche de fond annulée: Chapitre {chapter_id} non trouvé.")
            return

        logger.info(f"Tâche de fond : Démarrage de la génération pour le chapitre '{chapter.title}'")

        # 1. Crée et génère la leçon
        lesson_node = knowledge_graph_model.KnowledgeNode(
            chapter_id=chapter.id, title=chapter.title, node_type="Lesson",
            description=f"Leçon sur {chapter.title}", order=0, generation_status='pending'
        )
        db.add(lesson_node); db.commit(); db.refresh(lesson_node)
        
        # NOTE : Les appels à l'IA sont synchrones car la tâche de fond s'exécute dans un thread séparé.
        lesson_text_json = ai_service.generate_lesson_for_chapter(lesson_node.title, model_choice)
        lesson_data = safe_json_loads(lesson_text_json)

        if not lesson_data or "lesson_text" not in lesson_data:
            lesson_node.generation_status = 'failed'; db.commit(); return
        
        lesson_text = lesson_data["lesson_text"]
        lesson_node.content_json = lesson_data
        lesson_node.generation_status = 'completed'
        db.add(knowledge_component_model.KnowledgeComponent(
            node_id=lesson_node.id, component_type="lesson", content_json={"text": lesson_text}, order=0
        ))
        db.commit()

        # 2. Crée et génère l'exercice
        exercise_node = knowledge_graph_model.KnowledgeNode(
            chapter_id=chapter.id, title=f"Exercice : {lesson_node.title}", node_type="Exercise",
            description=f"Appliquez vos connaissances sur '{lesson_node.title}'.", order=1, generation_status='pending'
        )
        db.add(exercise_node); db.commit(); db.refresh(exercise_node)

        exercises_json = ai_service.generate_coding_exercises_from_lesson(lesson_node.title, lesson_text, model_choice)
        exercises_data = safe_json_loads(exercises_json)

        if not exercises_data or not exercises_data.get("exercises"):
            exercise_node.generation_status = 'failed'; db.commit(); return
        
        code_exercise = exercises_data["exercises"][0]
        db.add(knowledge_component_model.KnowledgeComponent(
            node_id=exercise_node.id, component_type="code", title=code_exercise.get("title"),
            content_json=code_exercise.get("content_json"), order=0
        ))
        exercise_node.generation_status = 'completed'
        chapter.is_generated = True
        db.commit()
        logger.info(f"✅ Tâche de fond : Contenu pour le chapitre '{chapter.title}' généré avec succès.")

    except Exception as e:
        logger.error(f"Erreur majeure dans la tâche de génération du chapitre {chapter_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


class ProgrammingCourseGenerator:
    def __init__(self, db: Session, db_course: course_model.Course, creator: user_model.User, background_tasks: BackgroundTasks):
        self.db = db
        self.db_course = db_course
        self.creator = creator
        self.background_tasks = background_tasks
        self.model_choice = db_course.model_choice

    def generate_full_course_scaffold(self):
        """
        Crée la structure du cours, met à jour le drapeau 'are_chapters_generated',
        et lance les tâches de fond pour générer le contenu.
        """
        logger.info(f"Gén. Prog. - Début de la structure pour '{self.db_course.title}'.")
        course_plan = self.db_course.learning_plan_json
        
        course_crud.enroll_user_in_course(self.db, self.db_course.id, self.creator.id)

        for level_idx, level_data in enumerate(course_plan.get("levels", [])):
            level = level_model.Level(
                course_id=self.db_course.id, 
                title=level_data.get("level_title"), 
                level_order=level_idx,
                are_chapters_generated=False # Le drapeau est initialement à False
            )
            self.db.add(level); self.db.commit(); self.db.refresh(level)

            chapter_titles = level_data.get("chapters", [])
            if not chapter_titles:
                logger.warning(f"Aucun chapitre trouvé dans le plan pour le niveau '{level.title}'")
                continue

            for chapter_idx, chapter_title in enumerate(chapter_titles):
                chapter = chapter_model.Chapter(
                    level_id=level.id, 
                    title=chapter_title, 
                    chapter_order=chapter_idx,
                    is_generated=False
                )
                self.db.add(chapter); self.db.commit(); self.db.refresh(chapter)
                
                logger.info(f"Programmation de la tâche de fond pour le chapitre : '{chapter.title}'")
                self.background_tasks.add_task(
                    generate_chapter_content_task, 
                    chapter.id, 
                    self.model_choice
                )
            
            # --- CORRECTION CRUCIALE ---
            # Une fois que tous les chapitres du niveau sont créés, on met le drapeau à jour.
            # Cela empêchera la logique JIT de se déclencher pour ce niveau.
            level.are_chapters_generated = True
            self.db.commit()
            # --------------------------
                
        self.db_course.generation_status = "completed"
        self.db.commit()
        logger.info(f"Structure du cours '{self.db_course.title}' créée. Les tâches sont en cours.")