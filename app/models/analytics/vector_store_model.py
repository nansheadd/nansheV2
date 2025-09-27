# Fichier: backend/app/models/analytics/vector_store_model.py (MODIFIÉ)
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.core.embeddings import EMBEDDING_DIMENSION

try:  # pragma: no cover - optional dependency when using SQLite locally
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - fallback for environments without pgvector
    Vector = None  # type: ignore

class VectorStore(Base):
    __tablename__ = 'vector_store'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Le texte de la définition (ex: "Apprendre à lire le japonais")
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    if Vector is not None:
        embedding: Mapped[List[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=True)
    else:  # pragma: no cover - fallback when pgvector is unavailable
        embedding: Mapped[List[float] | None] = mapped_column(JSONB, nullable=True)

    # --- NOUVELLES COLONNES POUR LA TAXONOMIE ---
    # Ces colonnes stockent la catégorie associée à ce vecteur
    domain: Mapped[str] = mapped_column(String(100), index=True)
    area: Mapped[str] = mapped_column(String(100), index=True)
    skill: Mapped[str] = mapped_column(String(100), index=True)

    metadata_: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=True)

    # ---------------------------------------------
    
    # Vous pouvez garder ces champs si vous en avez besoin pour d'autres usages
    source_language: Mapped[str] = mapped_column(String(50), nullable=True)
    content_type: Mapped[str] = mapped_column(String(50), default="taxonomy_definition")

    def __repr__(self):
        return f"<VectorStore(id={self.id}, skill='{self.skill}', text='{self.chunk_text[:30]}...')>"
