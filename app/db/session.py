# Fichier: nanshe/backend/app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

DATABASE_URL = str(settings.DATABASE_URL)

# Pour SQLite, on doit désactiver check_same_thread afin de permettre
# l'utilisation de la même connexion dans différents threads.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
