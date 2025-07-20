# Fichier: nanshe/backend/app/core/security.py (CORRIGÉ)

from datetime import datetime, timedelta, timezone # <--- On ajoute 'timezone'
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext

# --- Configuration de la Sécurité ---
SECRET_KEY = "a_very_secret_key_that_should_be_in_a_env_file"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Fonctions Utilitaires ---
def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """Crée un token d'accès JWT."""
    if expires_delta:
        # CORRIGÉ : On utilise .now(timezone.utc)
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # CORRIGÉ : On utilise .now(timezone.utc)
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si un mot de passe en clair correspond à un mot de passe haché."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hache un mot de passe."""
    return pwd_context.hash(password)