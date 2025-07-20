# Fichier: nanshe/backend/app/main.py
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import engine
from app.db.base_class import Base

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nanshe API V2",
    openapi_url="/api/v2/openapi.json"
)

origins = ["http://localhost:3000", "http://localhost:5173"] # Pour le frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Événement de Démarrage ---
@app.on_event("startup")
def on_startup():
    """
    Cet événement est déclenché au démarrage du serveur.
    Nous l'utilisons pour créer les tables de la base de données.
    """
    logger.info("Vérification et création des tables de la base de données...")
    try:
        # Cette commande magique crée toutes les tables qui héritent de `Base`
        # si elles n'existent pas déjà.
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Les tables de la base de données sont prêtes.")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des tables : {e}")

# --- Route Racine ---
@app.get("/")
def read_root():
    return {"message": "Welcome to Nanshe API V2!"}

# Note : On ajoutera les routeurs de l'API ici plus tard
# from app.api.v2.api import api_router
# app.include_router(api_router, prefix="/api/v2")