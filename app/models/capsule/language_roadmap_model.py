# Fichier: app/models/capsule/language_roadmap_model.py

from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.db.base_class import Base

if TYPE_CHECKING:
    from .capsule_model import Capsule

class LanguageRoadmapLevel(Base):
    """
    Représente un niveau structuré et gamifié dans le plan d'apprentissage
    d'une capsule de langue. Remplace le learning_plan_json.
    """
    __tablename__ = "language_roadmap_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Clé étrangère liant ce niveau à une capsule spécifique
    capsule_id: Mapped[int] = mapped_column(Integer, ForeignKey("capsules.id"), index=True)

    # --- Gamification & Progression ---
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(10), nullable=False) # Ex: "Pré-A1", "A1-", "B2+"
    xp_range_start: Mapped[int] = mapped_column(Integer, nullable=False)
    xp_range_end: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- Objectifs d'apprentissage quantitatifs ---
    target_vocabulary: Mapped[int] = mapped_column(Integer, default=0)
    target_grammar_rules: Mapped[int] = mapped_column(Integer, default=0)
    target_verbs: Mapped[int] = mapped_column(Integer, default=0)
    target_characters: Mapped[int] = mapped_column(Integer, default=0) # Kanji, Alphabet, etc.
    target_idioms: Mapped[int] = mapped_column(Integer, default=0)

    # --- Objectifs d'apprentissage qualitatifs ---
    pronunciation_focus: Mapped[str] = mapped_column(String(255)) # Ex: "Sons voyelles", "Intonation"
    mechanics_focus: Mapped[str] = mapped_column(String(255)) # Ex: "1–5", "Compteurs 人/枚 (jp)"
    connectors_focus: Mapped[str] = mapped_column(String(255)) # Ex: "Et", "Parce que"
    register_focus: Mapped[str] = mapped_column(String(255)) # Ex: "Salutations", "Présent simple poli"

    # --- Relation ---
    # Permet d'accéder à la capsule depuis un niveau de la roadmap
    capsule: Mapped["Capsule"] = relationship(back_populates="language_roadmap")

    def __repr__(self):
        return f"<RoadmapLevel(level={self.level}, cefr='{self.cefr_level}', capsule_id={self.capsule_id})>"