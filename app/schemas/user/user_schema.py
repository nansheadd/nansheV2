# Fichier: nanshe/backend/app/schemas/user_schema.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# --- Schéma de Base ---
# Contient les champs communs partagés par les autres schémas.
class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None

# --- Schéma pour la Création d'Utilisateur ---
# C'est ce que l'API attendra dans le corps d'une requête POST /users.
class UserCreate(UserBase):
    password: str

# --- Schéma pour la Mise à Jour d'Utilisateur ---
# Champs qu'un utilisateur peut mettre à jour sur son profil.
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None

# --- Schéma pour la Réponse de l'API ---
# C'est la forme des données utilisateur que l'API renverra.
# Note : Il n'y a PAS de mot de passe ici pour des raisons de sécurité.
class User(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime

    class Config:
        from_attributes = True # Permet à Pydantic de lire les modèles SQLAlchemy