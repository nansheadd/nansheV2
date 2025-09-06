# Fichier: backend/app/models/analytics/vector_store_model.py (MODIFIÉ)
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB  # <-- 1. Importez JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import Base
from pgvector.sqlalchemy import Vector # Assurez-vous d'importer Vector
from typing import Dict, Any

class VectorStore(Base):
    __tablename__ = 'vector_store'

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Le texte de la définition (ex: "Apprendre à lire le japonais")
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # L'embedding de ce texte
    embedding: Mapped[Vector] = mapped_column(Vector(384), nullable=False) # 384 pour 'all-MiniLM-L6-v2'

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