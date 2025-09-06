import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.user.user_model import User
from app.models.course.course_model import Course
from app.models.analytics.vector_store_model import VectorStore
from app.models.course.knowledge_graph_model import KnowledgeNode, KnowledgeEdge, NodeExercise
from app.crud.course import course_crud
from app.core import ai_service, prompt_manager
from app.core.ai_service import get_text_embedding

logger = logging.getLogger(__name__)


def _map_ai_exercise_to_db_format(ai_exercise: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Transforme intelligemment un exercice au format de l'IA vers notre format de BDD.
    Cette fonction est conçue pour être très flexible.
    """
    try:
        # 1. Extraire le titre (il peut avoir plusieurs noms)
        title = ai_exercise.get("title") or ai_exercise.get("titre") or ai_exercise.get("prompt") or ai_exercise.get("question") or ai_exercise.get("énoncé")

        # 2. Extraire la consigne (le prompt pour l'étudiant)
        prompt = ai_exercise.get("prompt") or ai_exercise.get("question") or ai_exercise.get("énoncé")

        # 3. Traduire le type d'exercice de manière flexible
        ai_type = ai_exercise.get("type", "").lower()
        component_type = "unknown"
        if "qcm" in ai_type or "multiple_choice" in ai_type:
            component_type = "qcm"
        elif "essay" in ai_type or "dissertation" in ai_type:
            component_type = "essay"
        elif "discussion" in ai_type or "débat" in ai_type or "critique" in ai_type:
            component_type = "discussion"
        elif "writing" in ai_type or "short_answer" in ai_type or "question courte" in ai_type:
            component_type = "writing"
        
        # 4. Construire le content_json
        content_json = {"prompt": prompt}
        if component_type == "qcm":
            content_json["choices"] = ai_exercise.get("options") or ai_exercise.get("choices")
            content_json["answer"] = ai_exercise.get("answer") or ai_exercise.get("réponse_attendue")

        # 5. Validation finale
        if not title or component_type == "unknown" or not content_json.get("prompt"):
            logger.warning(f"  -> Mapper : Exercice ignoré (infos essentielles manquantes). Données : {ai_exercise}")
            return None

        return {"title": str(title), "component_type": component_type, "content_json": content_json}
    except Exception as e:
        logger.error(f"  -> Mapper : Erreur de transformation. Erreur: {e}. Données : {ai_exercise}")
        return None


class PhilosophyCourseGenerator:
    """
    Orchestre la création d'un cours de philosophie basé sur un graphe de connaissances.
    """
    def __init__(self, db: Session, db_course: Course, creator: User):
        self.db = db
        self.db_course = db_course
        self.creator = creator
        self.model_choice = db_course.model_choice

    def generate_full_course_graph(self):
        """
        Méthode principale qui génère la structure et le contenu du graphe.
        """
        try:
            logger.info(f"Génération du graphe pour '{self.db_course.title}'...")
            
            graph_data = self._generate_graph_structure()
            nodes = self._save_graph_structure(graph_data)

            for node in nodes:
                try:
                    self._generate_and_process_node_content(node)
                except Exception as e:
                    logger.error(f"  -> ÉCHEC du traitement pour le nœud '{node.title}' (ID: {node.id}). Erreur: {e}", exc_info=True)
                    continue

            self.db_course.generation_status = "completed"
            self.db_course.generation_step = "Cours prêt !"
            self.db.commit()

            logger.info(f"Inscription du créateur {self.creator.id} au cours de philosophie {self.db_course.id}...")
            course_crud.enroll_user_in_course(
                db=self.db, 
                user_id=self.creator.id, 
                course_id=self.db_course.id
            )

            logger.info(f"Graphe et contenu pour '{self.db_course.title}' créés avec succès.")
            return self.db_course

        except Exception as e:
            logger.error(f"Erreur majeure (structure du graphe) pour '{self.db_course.title}': {e}", exc_info=True)
            self.db.rollback()
            self.db_course.generation_status = "failed"
            self.db.commit()
            return None

    def _generate_graph_structure(self) -> dict:
        """Appelle l'IA pour obtenir la structure du graphe."""
        logger.info("  -> Étape 1: Génération de la structure du graphe...")
        system_prompt = prompt_manager.get_prompt(
            "philosophy_generation.knowledge_graph",
            title=self.db_course.title
        )
        return ai_service._call_ai_model_json(
            user_prompt="Génère le graphe de connaissances.",
            model_choice=self.model_choice,
            system_prompt=system_prompt
        )

    def _save_graph_structure(self, graph_data: dict) -> List[KnowledgeNode]:
        """
        Peuple les tables KnowledgeNode et KnowledgeEdge et retourne la liste des nœuds créés.
        """
        logger.info("  -> Étape 2: Sauvegarde de la structure du graphe en base de données...")
        nodes_data = graph_data.get("nodes", [])
        edges_data = graph_data.get("edges", [])

        if not nodes_data:
            raise ValueError("L'IA n'a retourné aucun nœud pour le graphe.")

        ai_id_to_db_id = {}
        created_nodes = []

        for node_data in nodes_data:
            node = KnowledgeNode(
                course_id=self.db_course.id,
                title=node_data.get("title"),
                node_type=node_data.get("node_type"),
                description=node_data.get("description")
            )
            self.db.add(node)
            self.db.flush()
            ai_id_to_db_id[node_data.get("id")] = node.id
            created_nodes.append(node)

        for edge_data in edges_data:
            source_ai_id = edge_data.get("source")
            target_ai_id = edge_data.get("target")
            if source_ai_id in ai_id_to_db_id and target_ai_id in ai_id_to_db_id:
                edge = KnowledgeEdge(
                    source_node_id=ai_id_to_db_id[source_ai_id],
                    target_node_id=ai_id_to_db_id[target_ai_id],
                    relation_type=edge_data.get("relation_type")
                )
                self.db.add(edge)
        
        self.db.commit()
        return created_nodes

    def _generate_and_process_node_content(self, node: KnowledgeNode):
        """Génère le contenu, l'indexe et crée les exercices pour un nœud."""
        logger.info(f"  -> Étape 3: Traitement du nœud '{node.title}'...")
        
        system_prompt = prompt_manager.get_prompt(
            "philosophy_generation.node_content",
            title=node.title,
            node_type=node.node_type,
            description=node.description,
            ensure_json=True
        )
        content_data = ai_service._call_ai_model_json(
            user_prompt="Rédige le contenu de cette leçon.",
            model_choice=self.model_choice,
            system_prompt=system_prompt
        )
        lesson_text = content_data.get("lesson_text")

        if lesson_text:
            node.content_json = {"lesson_text": lesson_text}
            self.db.commit()
            self._index_node_content(node, lesson_text)
            self._generate_exercises_for_node(node, lesson_text)
        else:
            logger.warning(f"Aucun contenu de leçon généré pour le nœud {node.id}")

    def _index_node_content(self, node: KnowledgeNode, lesson_text: str):
        """Découpe une leçon en paragraphes et les indexe dans VectorStore."""
        logger.info(f"    -> Indexation du contenu pour le nœud {node.id}...")
        if not lesson_text: return

        chunks = [chunk.strip() for chunk in lesson_text.split('\n\n') if chunk.strip() and len(chunk) > 50]
        
        for chunk in chunks:
            embedding = get_text_embedding(chunk)
            vector_entry = VectorStore(
                knowledge_node_id=node.id, 
                chunk_text=chunk,
                embedding=embedding,
                source_language="francais",  # Ou la langue du cours si elle est définie
                content_type="philosophy_lesson_chunk"
            )
            self.db.add(vector_entry)
        
        self.db.commit()
        logger.info(f"      -> {len(chunks)} chunks indexés pour le nœud {node.id}.")

    def _generate_exercises_for_node(self, node: KnowledgeNode, lesson_text: str):
        """Génère les exercices pour un nœud de connaissance."""
        logger.info(f"    -> Tentative de génération des exercices pour le nœud {node.id}...")
        
        system_prompt = prompt_manager.get_prompt(
            "philosophy_generation.node_exercises",
            node_title=node.title,
            lesson_text=lesson_text, # On injecte la leçon ici
            ensure_json=True
        )
        
        exercises_data = ai_service._call_ai_model_json(
            user_prompt="Génère les exercices en te basant sur le contexte fourni.",
            model_choice=self.model_choice,
            system_prompt=system_prompt
        )

        exercises_list = exercises_data.get("exercises", [])
        if not exercises_list:
            logger.warning(f"      -> L'IA n'a pas retourné de liste d'exercices pour le nœud {node.id}. Réponse : {exercises_data}")
            return
            
        logger.info(f"      -> {len(exercises_list)} exercices reçus. Transformation et sauvegarde...")
        saved_count = 0
        for ai_exercise in exercises_list:
            clean_exercise_data = ai_exercise
            if clean_exercise_data:
                self.db.add(NodeExercise(node_id=node.id, **clean_exercise_data))
                saved_count += 1
        
        self.db.commit()
        logger.info(f"      -> {saved_count}/{len(exercises_list)} exercices ont été sauvegardés avec succès.")