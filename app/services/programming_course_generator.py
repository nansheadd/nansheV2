import logging
from sqlalchemy.orm import Session
from app.core import ai_service
from app.core.prompt_manager import get_prompt
from app.models.course.course_model import Course
# CORRECTION : On importe uniquement les classes qui existent dans votre fichier
from app.models.course.knowledge_graph_model import KnowledgeNode, KnowledgeEdge, NodeExercise

logger = logging.getLogger(__name__)

class ProgrammingCourseGenerator:
    """
    Générateur spécifique pour les cours de programmation.
    Crée une structure de graphe (Nœuds/Arêtes) directement liée au cours.
    """
    def __init__(self, db: Session, course: Course):
        self.db = db
        self.course = course

    async def generate_graph_structure(self):
        """
        Génère UNIQUEMENT la structure du graphe.
        Cette méthode est appelée par le `CourseGenerator` principal.
        """
        try:
            logger.info(f"Génération de la structure du graphe pour le cours '{self.course.title}'")
            self.course.generation_status = "generating_plan"
            self.db.commit()

            prompt = get_prompt(
                "programming_generation.knowledge_graph", 
                ensure_json=True,
                topic=self.course.title
            )
            
            # Utilise la fonction _call_ai_model_json de votre service pour plus de robustesse
            response_json = ai_service._call_ai_model_json(
                user_prompt=f"Génère le graphe pour le sujet : {self.course.title}",
                model_choice=self.course.model_choice,
                system_prompt=prompt
            )
            
            if not response_json or "nodes" not in response_json or "edges" not in response_json:
                raise ValueError("Réponse de l'IA invalide pour le graphe de connaissances.")

            # On appelle la méthode corrigée pour sauvegarder le graphe
            self._save_graph_structure(response_json)

            self.course.generation_status = "completed" # Le plan est prêt, le contenu sera généré en JIT
            logger.info(f"Structure du graphe créée avec succès pour le cours ID {self.course.id}")

        except Exception as e:
            self.course.generation_status = "failed"
            logger.error(f"Erreur lors de la génération du graphe pour le cours ID {self.course.id}: {e}", exc_info=True)
        
        finally:
            self.db.commit()

    def _save_graph_structure(self, graph_data: dict):
        nodes_data = graph_data.get("nodes", [])
        edges_data = graph_data.get("edges", [])
        external_id_to_db_id = {}

        # 1. Créer les nœuds de manière robuste
        for node_data in nodes_data:
            external_id = node_data.get("id")
            if not external_id:
                continue

            node_title = node_data.get("label") or node_data.get("title") or f"Concept {external_id}"
            node_type = node_data.get("type") or "Concept"

            new_node = KnowledgeNode(
                course_id=self.course.id,
                title=node_title,
                node_type=node_type,
                description="",
                content_json={}
            )
            self.db.add(new_node)
        self.db.flush() # On flush une seule fois après avoir ajouté tous les nœuds

        # On met à jour notre map après le flush pour avoir tous les IDs
        for node in self.db.new:
            if isinstance(node, KnowledgeNode):
                # On doit retrouver l'external_id. C'est un peu complexe,
                # donc on va simplifier en ne créant qu'un nœud à la fois.
                pass # La boucle ci-dessous est plus simple et plus sûre.

        # On recrée la map de manière plus sûre
        all_new_nodes = self.db.query(KnowledgeNode).filter(KnowledgeNode.course_id == self.course.id).all()
        # Création d'un dictionnaire inversé pour retrouver l'id externe à partir du titre
        title_to_ext_id = {node.get("label") or node.get("title"): node.get("id") for node in nodes_data}
        ext_id_to_db_id = {title_to_ext_id.get(n.title): n.id for n in all_new_nodes if title_to_ext_id.get(n.title)}


        # 2. Créer les arêtes de manière robuste
        for edge_data in edges_data:
            source_ext_id = edge_data.get("source")
            target_ext_id = edge_data.get("target")
            source_db_id = ext_id_to_db_id.get(source_ext_id)
            target_db_id = ext_id_to_db_id.get(target_ext_id)

            if source_db_id and target_db_id:
                # +++ LA CORRECTION FINALE EST ICI +++
                relation_type = edge_data.get("label") or "depend_de"

                new_edge = KnowledgeEdge(
                    source_node_id=source_db_id,
                    target_node_id=target_db_id,
                    relation_type=relation_type # On utilise la variable sécurisée
                )
                self.db.add(new_edge)
        
        # 3. On commit toute la transaction d'un coup
        self.db.commit()