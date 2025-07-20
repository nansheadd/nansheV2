# Fichier: nanshe/backend/app/db/base_class.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    Classe de base pour tous les modèles SQLAlchemy.
    Elle sera utilisée pour initialiser la base de données.
    """