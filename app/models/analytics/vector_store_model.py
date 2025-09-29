# Fichier: backend/app/models/analytics/vector_store_model.py (MODIFIÉ)
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.db.base_class import Base
from app.core.embeddings import EMBEDDING_DIMENSION

try:  # pragma: no cover - optional dependency when using SQLite locally
    from pgvector.sqlalchemy import Vector as PGVector
except ImportError:  # pragma: no cover - fallback for environments without pgvector
    PGVector = None  # type: ignore


class _VectorTextFallback(TypeDecorator):
    """Minimal vector storage that renders to the pgvector textual format.

    When the ``pgvector`` package is unavailable (which can happen on serverless
    platforms such as Vercel), SQLAlchemy would otherwise map the column to
    JSONB. Postgres refuses to coerce JSON to the ``vector`` type, which caused
    production inserts to fail. This lightweight fallback encodes any iterable
    of numbers to the canonical ``[v1, v2, ...]`` representation accepted by
    the pgvector extension while still returning Python ``list[float]`` values
    when rows are read back.
    """

    impl = Text
    cache_ok = True

    def __init__(self, dimension: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dimension = dimension

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            # Already formatted as pgvector text.
            return value
        try:
            floats = [float(item) for item in value]
        except TypeError as exc:  # pragma: no cover - defensive
            raise TypeError("Vector values must be iterable when pgvector is unavailable") from exc
        if self.dimension and len(floats) != self.dimension:
            # pgvector happily truncates/extends, but align here to avoid surprises.
            if len(floats) < self.dimension:
                floats.extend(0.0 for _ in range(self.dimension - len(floats)))
            else:
                floats = floats[: self.dimension]
        return "[" + ", ".join(f"{num:.12g}" for num in floats) + "]"

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return [float(item) for item in value]
        text_value = str(value).strip()
        if not text_value:
            return []
        if text_value.startswith("[") and text_value.endswith("]"):
            inner = text_value[1:-1].strip()
            if not inner:
                return []
            return [float(chunk.strip()) for chunk in inner.split(",") if chunk.strip()]
        # Fallback: try to split on whitespace.
        return [float(chunk) for chunk in text_value.split()] if text_value else []


Vector = PGVector or _VectorTextFallback  # type: ignore

class VectorStore(Base):
    __tablename__ = 'vector_store'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Le texte de la définition (ex: "Apprendre à lire le japonais")
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[List[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=True)

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
