from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

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

    class Config:
        from_attributes = True

class MoleculeRead(BaseModel):
    """Schéma pour lire une Molécule (un chapitre/une leçon)."""
    id: int
    title: str
    order: int
    atoms: List[AtomRead] = []

    class Config:
        from_attributes = True

class GranuleRead(BaseModel):
    """Schéma pour lire un Granule (un niveau)."""
    id: int
    title: str
    order: int
    molecules: List[MoleculeRead] = []

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
    xp: int = Field(..., description="Points d'expérience totaux pour cette capsule.")

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