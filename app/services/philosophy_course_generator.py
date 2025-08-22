import logging
from typing import List
from sqlalchemy.orm import Session
from app.models.user.user_model import User
from app.models.course.course_model import Course
from app.models.analytics.vector_store_model import VectorStore
from app.models.course.knowledge_graph_model import KnowledgeNode, KnowledgeEdge, NodeExercise
from app.core import ai_service, prompt_manager
from .tasks import generate_node_content_task

from app.core.ai_service import get_text_embedding

logger = logging.getLogger(__name__)

class PhilosophyCourseGenerator:
    """
    Orchestre la création d'un cours de philosophie basé sur un graphe de connaissances.
    """
    def __init__(self, db: Session, db_course: Course, creator: User):
        self.db = db
        self.db_course = db_course
        self.creator = creator
        self.model_choice = db_course.model_choice


    def generate_full_course_graph(self): # Renommée pour plus de clarté
        """
        Méthode principale qui génère la structure ET le contenu du graphe
        de manière séquentielle au sein d'une seule tâche de fond.
        """
        try:
            logger.info(f"Génération du graphe pour '{self.db_course.title}'...")
            
            graph_data = self._generate_graph_structure()
            nodes = self._save_graph_structure(graph_data)

            # On boucle directement ici, au sein de la même tâche
            for node in nodes:
                self._generate_and_process_node_content(node)

            # Mettre à jour le statut final du cours
            self.db_course.generation_status = "completed"
            self.db_course.generation_step = "Cours prêt !"
            self.db.commit()

            logger.info(f"Graphe et contenu pour '{self.db_course.title}' créés avec succès.")
            return self.db_course


        except Exception as e:
            logger.error(f"Erreur majeure lors de la génération du graphe pour le cours '{self.db_course.title}': {e}", exc_info=True)
            self.db_course.generation_status = "failed"
            self.db.commit()
            return None

    def _generate_graph_structure(self) -> dict:
        """Appelle l'IA pour obtenir la structure du graphe."""
        logger.info("  -> Étape 1: Génération de la structure du graphe...")
        system_prompt = prompt_manager.get_prompt(
            "philosophy_generation.knowledge_graph",
            title=self.db_course.title,
            ensure_json=True
        )
        return ai_service._call_ai_model_json(
            user_prompt=f"Génère le graphe de connaissances pour {self.db_course.title}",
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
            else:
                logger.warning(f"Arête ignorée car un de ses nœuds n'existe pas : {edge_data}")
        
        self.db.commit()
        return created_nodes

    def _generate_exercises_for_node(self, node: KnowledgeNode, lesson_text: str):
        logger.info(f"    -> Tentative de génération des exercices pour le nœud {node.id}...")
        
        system_prompt = prompt_manager.get_prompt(
            "philosophy_generation.node_exercises",
            lesson_text=lesson_text, node_title=node.title, ensure_json=True
        )
        exercises_data = ai_service._call_ai_model_json(
            user_prompt="Génère les exercices pour cette leçon.",
            model_choice=self.model_choice, system_prompt=system_prompt
        )

        # --- AJOUT DE LOGS ET DE VÉRIFICATIONS ---
        if not exercises_data or "exercises" not in exercises_data or not isinstance(exercises_data["exercises"], list):
            logger.warning(f"      -> L'IA n'a pas retourné une liste d'exercices valide pour le nœud {node.id}. Réponse reçue : {exercises_data}")
            return # On quitte la fonction pour éviter une erreur

        exercises_list = exercises_data.get("exercises", [])
        logger.info(f"      -> {len(exercises_list)} exercices reçus de l'IA.")

        for ex_data in exercises_list:
            if not all(k in ex_data for k in ["title", "component_type", "content_json"]):
                logger.warning(f"        -> Exercice ignoré car il manque des clés : {ex_data}")
                continue

            exercise = NodeExercise(
                node_id=node.id, title=ex_data.get("title"),
                component_type=ex_data.get("component_type"),
                content_json=ex_data.get("content_json", {})
            )
            self.db.add(exercise)
        
        self.db.commit()
        logger.info(f"      -> Exercices sauvegardés pour le nœud {node.id}.")


    def _generate_and_process_node_content(self, node: KnowledgeNode):
        """Génère le contenu, l'indexe et crée les exercices pour un nœud."""
        logger.info(f"  -> Étape 3: Traitement du nœud '{node.title}'...")
        
        # Générer le contenu de la leçon
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
        lesson_text = content_data.get("lesson_text", "")

        if lesson_text:
            node.content_json = {"lesson_text": lesson_text}
            self.db.commit()

            # Indexer le contenu dans la DB vectorielle
            self._index_node_content(node, lesson_text)
            
            # Générer les exercices basés sur la leçon
            self._generate_exercises_for_node(node, lesson_text)
        else:
            logger.warning(f"Aucun contenu de leçon généré pour le nœud {node.id}")

    def _index_node_content(self, node: KnowledgeNode, lesson_text: str):
        """Découpe une leçon en paragraphes et les indexe dans VectorStore."""
        # The parameter is now correctly named `node`
        logger.info(f"    -> Indexation du contenu pour le nœud {node.id}...")
        if not lesson_text: return

        chunks = [chunk.strip() for chunk in lesson_text.split('\n\n') if chunk.strip()]
        
        for chunk in chunks:
            if len(chunk) < 50: continue
            
            embedding = get_text_embedding(chunk)
            vector_entry = VectorStore(
                # On passe `node.id` (l'entier) et non `node` (l'objet)
                knowledge_node_id=node.id, 
                chunk_text=chunk,
                embedding=embedding
            )
            self.db.add(vector_entry)
        
        self.db.commit()
        logger.info(f"      -> {len(chunks)} chunks indexés pour le nœud {node.id}.")

        
    def _generate_exercises_for_node(self, node: KnowledgeNode, lesson_text: str):
        """Génère les exercices pour un nœud de connaissance."""
        logger.info(f"    -> Génération des exercices pour le nœud {node.id}...")
        
        system_prompt = prompt_manager.get_prompt(
            "philosophy_generation.node_exercises",
            lesson_text=lesson_text,
            node_title=node.title,
            ensure_json=True
        )
        exercises_data = ai_service._call_ai_model_json(
            user_prompt="Génère les exercices pour cette leçon.",
            model_choice=self.model_choice,
            system_prompt=system_prompt
        )

        for ex_data in exercises_data.get("exercises", []):
            exercise = NodeExercise(
                node_id=node.id,
                title=ex_data.get("title", "Exercice"),
                component_type=ex_data.get("component_type", "unknown"),
                content_json=ex_data.get("content_json", {})
            )
            self.db.add(exercise)
        
        self.db.commit()