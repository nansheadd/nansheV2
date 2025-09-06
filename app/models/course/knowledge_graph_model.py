# Fichier : backend/app/models/course/knowledge_graph_model.py (CORRIGÉ)

from sqlalchemy import Integer, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .course_model import Course
    from ..progress.user_answer_log_model import UserAnswerLog

# On définit NodeExercise en premier
class NodeExercise(Base):
    __tablename__ = "node_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    node_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"))
    
    title: Mapped[str] = mapped_column(Text, nullable=False)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    node: Mapped["KnowledgeNode"] = relationship(back_populates="exercises")
    user_answers: Mapped[List["UserAnswerLog"]] = relationship(back_populates="node_exercise")

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        """Return a readable representation for admin interfaces."""
        return f"<NodeExercise id={self.id} title='{self.title}'>"


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"))
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=True)

    course: Mapped["Course"] = relationship(back_populates="knowledge_nodes")
    
    outgoing_edges: Mapped[List["KnowledgeEdge"]] = relationship(
        "KnowledgeEdge", foreign_keys="[KnowledgeEdge.source_node_id]", back_populates="source_node", cascade="all, delete-orphan"
    )
    incoming_edges: Mapped[List["KnowledgeEdge"]] = relationship(
        "KnowledgeEdge", foreign_keys="[KnowledgeEdge.target_node_id]", back_populates="target_node", cascade="all, delete-orphan"
    )
    
    # --- C'EST CETTE RELATION QUI DOIT ÊTRE PRÉSENTE ---
    exercises: Mapped[List["NodeExercise"]] = relationship(
        "NodeExercise", back_populates="node", cascade="all, delete-orphan"
    )
    # ----------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        """Return a readable representation for admin interfaces."""
        return f"<KnowledgeNode id={self.id} title='{self.title}'>"


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False)

    source_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"))
    target_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"))

    source_node: Mapped["KnowledgeNode"] = relationship(
        "KnowledgeNode", foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target_node: Mapped["KnowledgeNode"] = relationship(
        "KnowledgeNode", foreign_keys=[target_node_id], back_populates="incoming_edges"
    )

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        """Return a readable representation for admin interfaces."""
        return (
            f"<KnowledgeEdge id={self.id} source={self.source_node_id} "
            f"target={self.target_node_id} type='{self.relation_type}'>"
        )