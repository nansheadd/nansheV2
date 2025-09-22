from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any

from app.models.capsule.capsule_model import GenerationStatus

# ==============================================================================
# SECTION 1: SCHÉMAS DE CONTENU (ATOM, MOLECULE, GRANULE)
# ==============================================================================

class AtomRead(BaseModel):
    """Schéma pour lire un Atome (le contenu pédagogique)."""
    id: int
    title: str
    order: int
    content_type: str
    content: Dict[str, Any]
    difficulty: Optional[str] = None
    progress_status: str = "not_started"
    is_locked: bool = False
    is_bonus: bool = False
    xp_value: int = 0
    capsule_id: Optional[int] = None
    molecule_id: Optional[int] = None
    user_feedback_rating: Optional[str] = None
    user_feedback_reason: Optional[str] = None
    user_feedback_comment: Optional[str] = None

    class Config:
        from_attributes = True

class MoleculeRead(BaseModel):
    """Schéma pour lire une Molécule (un chapitre/une leçon)."""
    id: int
    title: str
    order: int
    atoms: List[AtomRead] = []
    generation_status: GenerationStatus
    progress_status: str = "not_started"
    is_locked: bool = False
    xp_total: int = 0
    xp_earned: int = 0
    xp_percent: float = 0.0
    bonus_xp_total: int = 0
    bonus_xp_earned: int = 0
    user_feedback_rating: Optional[str] = None
    user_feedback_reason: Optional[str] = None
    user_feedback_comment: Optional[str] = None

    class Config:
        from_attributes = True

class GranuleRead(BaseModel):
    """Schéma pour lire un Granule (un niveau)."""
    id: int
    title: str
    order: int
    molecules: List[MoleculeRead] = []
    progress_status: str = "not_started"
    is_locked: bool = False
    xp_total: int = 0
    xp_earned: int = 0
    xp_percent: float = 0.0
    bonus_xp_total: int = 0
    bonus_xp_earned: int = 0

    class Config:
        from_attributes = True

# ==============================================================================
# SECTION 2: SCHÉMAS DE LA CAPSULE
# ==============================================================================

class CapsuleCreate(BaseModel):
    """Ce que le frontend envoie pour créer une capsule."""
    title: str

class CapsuleRead(BaseModel):
    """
    Schéma complet pour lire les données d'une capsule.
    Utilisé pour la page de détail.
    """
    id: int
    title: str
    description: Optional[str] = None
    domain: str
    area: str
    main_skill: str
    is_public: bool
    generation_status: str
    learning_plan_json: Optional[Dict[str, Any]] = None
    granules: List[GranuleRead] = []
    user_xp: Optional[int] = None
    user_bonus_xp: Optional[int] = None
    xp_target: Optional[int] = None
    xp_percent: float = 0.0
    xp_remaining: Optional[int] = None
    bonus_xp_total: Optional[int] = None
    bonus_xp_earned: Optional[int] = None
    bonus_xp_remaining: Optional[int] = None

    # On peut aussi inclure les granules si nécessaire
    # granules: List[GranuleRead] = []

    class Config:
        from_attributes = True

# ==============================================================================
# SECTION 3: SCHÉMAS DE PROGRESSION & UTILITAIRES
# ==============================================================================

class SkillBase(BaseModel):
    name: str
    description: Optional[str] = None

class SkillRead(SkillBase):
    id: int

    class Config:
        from_attributes = True

class CapsuleProgressRead(BaseModel):
    """
    Schéma pour lire la progression d'un utilisateur sur une capsule.
    Utilisé par le nouveau `progress_router`.
    """
    id: int
    user_id: int
    capsule_id: int
    skill_id: int
    xp: int = Field(..., description="Points d'expérience totaux pour cette capsule.")
    bonus_xp: int = 0
    strength: float

    class Config:
        from_attributes = True

# ==============================================================================
# SECTION 4: SCHÉMAS POUR LES SESSIONS D'APPRENTISSAGE
# ==============================================================================

class LearningSessionMolecule(BaseModel):
    """Représente une molécule dans le contexte d'une session."""
    molecule_title: str
    atoms: List[Dict[str, Any]] # On garde un format flexible pour le frontend

class LearningSessionRead(BaseModel):
    """
    Schéma pour la réponse de l'endpoint qui prépare une session.
    """
    granule_title: str
    molecules: List[LearningSessionMolecule]

class LanguageRoadmapRead(BaseModel):
    id: int
    roadmap_data: Dict[str, Any]

    class Config:
        from_attributes = True

# Schéma principal qui combine Capsule et Roadmap
class CapsuleReadWithRoadmap(CapsuleRead): # Assurez-vous que CapsuleRead existe déjà
    language_roadmap: LanguageRoadmapRead | None = None


# ==============================================================================
# SECTION 5: SCHÉMAS DE CRÉATION (AJOUTS NÉCESSAIRES)
# ==============================================================================
from app.models.capsule.atom_model import AtomContentType

class AtomCreate(BaseModel):
    """Schéma pour la création d'un nouvel Atome."""
    title: str
    order: int
    content_type: AtomContentType  # On utilise l'Enum de votre modèle
    content: Dict[str, Any]
    difficulty: Optional[str] = None
    molecule_id: int

class MoleculeCreate(BaseModel):
    """Schéma pour la création d'une nouvelle Molécule."""
    title: str
    order: int
    granule_id: int

class GranuleCreate(BaseModel):
    """Schéma pour la création d'un nouveau Granule."""
    title: str
    order: int
    capsule_id: int

# Renommons votre CapsuleCreate en CapsuleCreateRequest pour être plus explicite
# sur le fait que c'est une requête de l'utilisateur.
class CapsuleCreateRequest(BaseModel):
    """
    Schéma mis à jour pour correspondre au résultat de la classification
    que le frontend envoie.
    """
    main_skill: str
    domain: str
    area: str
    # On peut ajouter d'autres champs si nécessaire
    # confidence: float
    # input_text: str


class CapsuleCreateInternal(BaseModel):
    """Utilisé par le service pour créer la capsule dans la base de données."""
    title: str
    owner_id: int
    # Ajoutez ici les champs de votre modèle Capsule qui sont obligatoires
    # Par exemple, si `domain`, `area`, `main_skill` sont requis.
    # Pour l'instant, on reste simple.
    description: Optional[str] = None


class MoleculeBonusRequest(BaseModel):
    kind: str
    difficulty: Optional[str] = None
    title: Optional[str] = None


# ==============================================================================
# SECTION 6: SCHÉMAS POUR LA CLASSIFICATION / FEEDBACK
# ==============================================================================


class ClassificationOptionDomain(BaseModel):
    domain: str
    areas: List[str] = []


class ClassificationOptionsResponse(BaseModel):
    domains: List[ClassificationOptionDomain]


class ClassificationFeedbackRequest(BaseModel):
    input_text: str
    predicted_domain: Optional[str] = None
    predicted_area: Optional[str] = None
    predicted_skill: Optional[str] = None
    is_correct: bool
    final_domain: Optional[str] = None
    final_area: Optional[str] = None
    final_skill: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def _validate_fields(self):
        if not self.input_text or not self.input_text.strip():
            raise ValueError("Le texte d'entrée ne peut pas être vide.")
        if not self.is_correct:
            if not self.final_domain or not self.final_domain.strip():
                raise ValueError("final_domain est requis lorsque la classification est corrigée.")
            if not self.final_area or not self.final_area.strip():
                raise ValueError("final_area est requis lorsque la classification est corrigée.")
        return self


class ClassificationFeedbackResponse(BaseModel):
    feedback_id: int
    training_entry_id: int
    input_text: str
    domain: str
    area: str
    main_skill: Optional[str] = None
    added_to_training: bool
    taxonomy: ClassificationOptionsResponse
    created_at: datetime
