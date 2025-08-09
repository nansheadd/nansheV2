# Fichier: backend/app/schemas/level_schema.py (CORRIGÉ)
from pydantic import BaseModel
from typing import List
# On importe le schéma Chapter pour la relation
from .chapter_schema import Chapter

class Level(BaseModel):
    """
    Schéma pour renvoyer les données d'un niveau, incluant sa liste de chapitres.
    """
    id: int
    title: str
    level_order: int
    
    # --- CORRECTION ICI ---
    # On utilise le nom de champ correct du modèle SQLAlchemy
    are_chapters_generated: bool
    # --- FIN DE LA CORRECTION ---
    course_id: int
    
    # On utilise une référence anticipée pour éviter les imports circulaires
    chapters: List['Chapter'] = []
    is_accessible: bool = False

    class Config:
        from_attributes = True

# On dit à Pydantic de résoudre les références anticipées
Level.model_rebuild()