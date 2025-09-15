# Fichier: app/models/capsule/language_roadmap_models.py

import enum
from sqlalchemy import (
    Integer, String, ForeignKey, Enum, UniqueConstraint, JSON, Boolean, Float, CheckConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, TYPE_CHECKING

from app.db.base_class import Base

if TYPE_CHECKING:
    from .capsule_model import Capsule
    from ..user.user_model import User

# --- Énumérations pour la clarté et la cohérence ---

class CEFRBand(enum.Enum):
    preA1 = "Pre-A1"
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class FocusType(enum.Enum):
    pronunciation = "pronunciation"
    mechanics = "mechanics"
    connectors = "connectors"
    register = "register"
    culture = "culture"

class SkillType(enum.Enum):
    core = "core"
    subskill = "subskill"
    extra_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})


class Unit(enum.Enum):
    items = "items"
    rules = "rules"
    verbs = "verbs"
    chars = "chars"
    accuracy = "accuracy"
    minutes = "minutes"
    tasks = "tasks"
    rubric = "rubric"
    none = "none"

class TargetMeasurement(enum.Enum):
    cumulative = "cumulative"
    at_level = "at_level"
    benchmark = "benchmark"
    time_on_task = "time_on_task"

class CheckType(enum.Enum):
    quiz = "quiz"
    oral = "oral"
    writing = "writing"
    performance = "performance"

class RewardType(enum.Enum):
    badge = "badge"
    title = "title"
    unlock = "unlock"


# --- Table centrale de la Roadmap ---
class LanguageRoadmap(Base):
    __tablename__ = "language_roadmaps"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    capsule_id: Mapped[int] = mapped_column(Integer, ForeignKey("capsules.id"), index=True)

    # Cette colonne peut stocker le plan JSON complet généré par l'IA
    roadmap_data: Mapped[dict] = mapped_column(JSON, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "capsule_id", name="uq_user_capsule_roadmap"),)

    # --- Relations ---
    user: Mapped["User"] = relationship(back_populates="roadmaps")
    capsule: Mapped["Capsule"] = relationship(back_populates="roadmaps")
    levels: Mapped[List["LanguageRoadmapLevel"]] = relationship(back_populates="roadmap", cascade="all, delete-orphan")


# --- MODÈLE LanguageRoadmapLevel (ENTIÈREMENT REFAIT) ---
class LanguageRoadmapLevel(Base):
    """
    Représente un niveau SPÉCIFIQUE à la feuille de route d'un utilisateur.
    Chaque niveau contient des objectifs, des focus, des récompenses, etc.
    """
    __tablename__ = "language_roadmap_levels"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # --- LA CORRECTION CLÉ ---
    # La colonne `capsule_id` est remplacée par `roadmap_id`.
    # Chaque niveau appartient maintenant à une feuille de route personnelle.
    roadmap_id: Mapped[int] = mapped_column(Integer, ForeignKey("language_roadmaps.id"), index=True)

    # --- Colonnes de données du niveau ---
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    cefr_level: Mapped[CEFRBand] = mapped_column(Enum(CEFRBand), nullable=False)
    xp_range_start: Mapped[int] = mapped_column(Integer, nullable=False)
    xp_range_end: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # --- Contraintes de la table ---
    __table_args__ = (
        UniqueConstraint("roadmap_id", "level", name="uq_roadmap_level"),
        CheckConstraint("xp_range_end > xp_range_start", name="ck_xp_range"),
    )

    # --- Relations ---
    # Relation vers le parent (la feuille de route personnelle)
    roadmap: Mapped["LanguageRoadmap"] = relationship(back_populates="levels")
    
    # Relations vers les enfants (les détails du niveau)
    focuses: Mapped[List["LevelFocus"]] = relationship(back_populates="level", cascade="all, delete-orphan")
    skill_targets: Mapped[List["LevelSkillTarget"]] = relationship(back_populates="level", cascade="all, delete-orphan")
    checkpoints: Mapped[List["LevelCheckpoint"]] = relationship(back_populates="level", cascade="all, delete-orphan")
    rewards: Mapped[List["LevelReward"]] = relationship(back_populates="level", cascade="all, delete-orphan")



# --- Tables de Liaison (Many-to-Many) ---

class LevelSkillTarget(Base):
    """Définit un objectif pour une compétence donnée à un certain niveau."""
    __tablename__ = "level_skill_targets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("language_roadmap_levels.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)

    target_value: Mapped[float] = mapped_column(Float, default=0.0)
    measurement: Mapped[TargetMeasurement] = mapped_column(Enum(TargetMeasurement), default=TargetMeasurement.cumulative)
    criteria: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    min_required: Mapped[bool] = mapped_column(Boolean, default=False)
    min_value: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (UniqueConstraint("level_id", "skill_id", name="uq_level_skill"),)

    level: Mapped["LanguageRoadmapLevel"] = relationship(back_populates="skill_targets")
    skill: Mapped["Skill"] = relationship()


class Skill(Base):
    """Référentiel central de toutes les compétences enseignables."""
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[SkillType] = mapped_column(Enum(SkillType), nullable=False, default=SkillType.core)
    unit: Mapped[Unit] = mapped_column(Enum(Unit), nullable=False, default=Unit.items)
    description: Mapped[str] = mapped_column(String(512), default="")
    extra_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})
                                             

class LevelFocus(Base):
    """Définit un focus qualitatif pour un niveau."""
    __tablename__ = "level_focuses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("language_roadmap_levels.id"), index=True)
    type: Mapped[FocusType] = mapped_column(Enum(FocusType), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=lambda: {})

    level: Mapped["LanguageRoadmapLevel"] = relationship(back_populates="focuses")

class LevelCheckpoint(Base):
    """Définit une évaluation ou une mission pour valider un niveau."""
    __tablename__ = "level_checkpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("language_roadmap_levels.id"), index=True)
    type: Mapped[CheckType] = mapped_column(Enum(CheckType), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    rubric: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    min_score: Mapped[float] = mapped_column(Float, default=0.0)
    links: Mapped[dict] = mapped_column(JSON, default=lambda: {})

    level: Mapped["LanguageRoadmapLevel"] = relationship(back_populates="checkpoints")

class LevelReward(Base):
    """Définit une récompense (badge, etc.) obtenue à un certain niveau."""
    __tablename__ = "level_rewards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("language_roadmap_levels.id"), index=True)
    type: Mapped[RewardType] = mapped_column(Enum(RewardType), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    extra_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})


    level: Mapped["LanguageRoadmapLevel"] = relationship(back_populates="rewards")