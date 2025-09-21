import enum
from sqlalchemy import Integer, String, ForeignKey, JSON, Enum as EnumSQL, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Dict, Any, TYPE_CHECKING, Optional

from app.db.base_class import Base

if TYPE_CHECKING:
    from .molecule_model import Molecule

class AtomContentType(str, enum.Enum):
    # --- 1. Atomes de FONDATION (Core Knowledge) ---
    LESSON = "lesson"                     # Texte principal d'une leçon (Markdown)
    VOCABULARY = "vocabulary"             # Liste de mots de vocabulaire
    GRAMMAR = "grammar"                   # Règle de grammaire spécifique
    CHARACTER = "character"               # Présentation d'un caractère (Kanji, etc.)
    CONCEPT_DEFINITION = "concept_definition" # Définition d'un concept, auteur, école (Philo)
    SYNTAX_REFERENCE = "syntax_reference" # Syntaxe brute d'une structure de code (Prog)
    CODE_EXAMPLE = "code_example"         # Bloc de code commenté et expliqué (Prog)

    # --- 2. Atomes de PRATIQUE GUIDÉE (Guided Practice) ---
    FILL_IN_THE_BLANK = "fill_in_the_blank" # Exercice de type "texte à trous"
    FLASHCARDS = "flashcards"             # Cartes de mémorisation interactives
    TRANSLATION = "translation"           # Exercice de traduction
    CODE_REFACTOR = "code_refactor"       # Exercice de réécriture de code (Prog)
    ARGUMENT_MAPPING = "argument_mapping" # Associer des arguments à des concepts (Philo)

    # --- 3. Atomes d'EXPRESSION & CRÉATIVITÉ (Creative Expression) ---
    DIALOGUE = "dialogue"                 # Conversation simulée, dialogue interactif
    ESSAY_PROMPT = "essay_prompt"         # Sujet de dissertation ouvert (Philo)
    DEBATE_PROMPT = "debate_prompt"       # Sujet de débat opposant deux concepts (Philo)
    CODE_CHALLENGE = "code_challenge"     # Mini-projet de programmation (Prog)
    LIVE_CODE_EXECUTOR = "live_code_executor" # Environnement d'exécution de code (Prog)
    CODE_SANDBOX_SETUP = "code_sandbox_setup" # Instructions pour ouvrir l'IDE/terminal sécurisé (Prog)
    CODE_PROJECT_BRIEF = "code_project_brief" # Projet de validation guidé pour une molécule (Prog)

    # --- 4. Atomes d'ÉVALUATION (Assessment) ---
    QUIZ = "quiz"                         # QCM, Vrai/Faux, réponses courtes
    EXERCISE = "exercise"                 # Exercice plus complexe à correction auto
    PEER_REVIEW = "peer_review"           # Évaluation par les pairs (Philo)
    COMPREHENSION_TEST = "comprehension_test" # Test de compréhension sur un texte/dialogue

class Atom(Base):
    """Représente un bloc de contenu indivisible (leçon, quiz) à l'intérieur d'une Molecule."""
    __tablename__ = "atoms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[AtomContentType] = mapped_column(
        EnumSQL(AtomContentType, name="atom_content_type_enum"), nullable=False
    )
    content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    difficulty: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    molecule_id: Mapped[int] = mapped_column(Integer, ForeignKey("molecules.id"))
    is_bonus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    
    # --- Relations ---
    molecule: Mapped["Molecule"] = relationship(back_populates="atoms")

    def __repr__(self):
        return f"<◾️Atom(id={self.id}, title='{self.title}', type='{self.content_type}')>"
