# Fichier: nanshe/backend/app/crud/user_crud.py

from sqlalchemy.orm import Session
from app.models.capsule.utility_models import UserCapsuleProgress
from app.models.user.user_model import User
from app.schemas.user.user_schema import UserCreate
from app.core.security import get_password_hash
from typing import Optional

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Récupère un utilisateur par son adresse email.

    Args:
        db: La session de base de données.
        email: L'email de l'utilisateur à rechercher.

    Returns:
        L'objet User s'il est trouvé, sinon None.
    """
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Récupère un utilisateur par son nom d'utilisateur.

    Args:
        db: La session de base de données.
        username: Le nom d'utilisateur à rechercher.

    Returns:
        L'objet User s'il est trouvé, sinon None.
    """
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, user: UserCreate) -> User:
    """
    Crée un nouvel utilisateur dans la base de données.

    Args:
        db: La session de base de données.
        user: L'objet UserCreate contenant les données du nouvel utilisateur.

    Returns:
        L'objet User qui vient d'être créé.
    """
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_capsule_progresses(db: Session, user_id: int) -> list[UserCapsuleProgress]:
    """Renvoie la progression de l'utilisateur pour chacune de ses capsules."""

    return (
        db.query(UserCapsuleProgress)
        .filter(UserCapsuleProgress.user_id == user_id)
        .order_by(UserCapsuleProgress.capsule_id.asc())
        .all()
    )
