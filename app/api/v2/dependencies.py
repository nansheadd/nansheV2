# Fichier: nanshe/backend/app/api/v2/dependencies.py
from app.db.session import SessionLocal

def get_db():
    """
    Dépendance FastAPI pour obtenir une session de base de données.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()