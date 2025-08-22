# Fichier: backend/app/schemas/course/knowledge_graph_schema.py

from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class NodeExercise(BaseModel):
    id: int
    title: str
    component_type: str
    content_json: Dict[str, Any]

    class Config:
        from_attributes = True


class KnowledgeNode(BaseModel):
    id: int
    course_id: int
    title: str
    node_type: str
    description: str
    
    # --- LA CORRECTION EST ICI ---
    content_json: Optional[Dict[str, Any]] = None # <-- 2. Rendre le champ optionnel
    exercises: List[NodeExercise] = []

    class Config:
        from_attributes = True

class KnowledgeEdge(BaseModel):
    id: int
    source_node_id: int
    target_node_id: int
    relation_type: str

    class Config:
        from_attributes = True

class KnowledgeGraph(BaseModel):
    course_title: str
    nodes: List[KnowledgeNode] = []
    edges: List[KnowledgeEdge] = []