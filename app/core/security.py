# Fichier: nanshe/backend/app/core/security.py (CORRIGÉ)

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Union

from jose import jwt
from passlib import exc as passlib_exc
from passlib.context import CryptContext

from app.core.config import settings

# --- Configuration de la Sécurité ---
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# --- Fonctions Utilitaires ---
def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """Crée un token d'accès JWT."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str | None, hashed_password: str | None) -> bool:
    """Vérifie si un mot de passe en clair correspond à un mot de passe haché."""

    if not plain_password or not hashed_password:
        return False

    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError, passlib_exc.PasslibError) as exc:
        logger.warning("Password verification failed: %s", exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Unexpected password verification error: %s", exc)
        return False

def get_password_hash(password: str) -> str:
    """Hache un mot de passe."""
    return pwd_context.hash(password)

