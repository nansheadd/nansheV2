from sqlalchemy import Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base
from pgvector.sqlalchemy import Vector
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..course.knowledge_graph_model import KnowledgeNode

class VectorStore(Base):
    __tablename__ = "vector_store"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # --- MISE À JOUR ---
    # Un chunk peut appartenir soit à un chapitre (langue), soit à un nœud (philosophie)
    # On les rend optionnels pour permettre cette flexibilité.
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"), nullable=True)
    knowledge_node_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_nodes.id"), nullable=True)
    # -------------------

    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))

    # Relations optionnelles
    knowledge_node: Mapped["KnowledgeNode"] = relationship()