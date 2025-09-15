# Fichier: nanshev3/backend/app/crud/roadmap_crud.py

from sqlalchemy.orm import Session
from app.models.capsule import language_roadmap_model
from typing import Dict, Any

def get_roadmap_by_user_and_capsule(db: Session, user_id: int, capsule_id: int):
    """Récupère une roadmap en utilisant le bon modèle."""
    # On interroge LanguageRoadmap, qui contient bien user_id et capsule_id
    return db.query(language_roadmap_model.LanguageRoadmap).filter_by(
        user_id=user_id,
        capsule_id=capsule_id
    ).first()

def create_roadmap(db: Session, user_id: int, capsule_id: int, plan_data: Dict[str, Any]):
    """Crée et sauvegarde une nouvelle roadmap."""
    new_roadmap = language_roadmap_model.LanguageRoadmap(
        user_id=user_id,
        capsule_id=capsule_id,
        roadmap_data=plan_data  # On sauvegarde le JSON directement
    )
    db.add(new_roadmap)
    db.commit()
    db.refresh(new_roadmap)
    return new_roadmap