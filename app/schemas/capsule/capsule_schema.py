from pydantic import BaseModel, Field
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
    domain: str = "Generic"
    area: str = "General Knowledge"
    main_skill: str = "Learning"
    is_public: bool = False
    generation_status: str = "PLANNING"
