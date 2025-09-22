# Fichier: nanshe/backend/app/schemas/user_schema.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# --- import models ---
from app.models.user.user_model import SubscriptionStatus
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
    is_email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    active_title: Optional[str] = None
    profile_border_color: Optional[str] = None
    xp_points: int
    level: int
    subscription_status: SubscriptionStatus = SubscriptionStatus.FREE
    stripe_customer_id: Optional[str] = None
    account_deletion_requested_at: Optional[datetime] = None
    account_deletion_scheduled_at: Optional[datetime] = None

    class Config:
        from_attributes = True # Permet à Pydantic de lire les modèles SQLAlchemy
