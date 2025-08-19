# Fichier: nanshe/backend/app/main.py (VERSION FINALE AVEC SQLADMIN ET PGVECTOR FIX)
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Imports de l'application
from app.core.config import settings
from app.db.base_class import Base
from app.api.v2.api import api_router
from app.core.security import verify_password
from app.models.user.user_model import User
from app.db.session import async_engine, SessionLocal

# Imports pour SQLAdmin
from sqladmin import Admin
from sqladmin.authentication import AuthenticationBackend
from app.admin import UserAdmin, CourseAdmin, AITokenLogAdmin, FeedbackAdmin

# --- NOUVEL IMPORT ---
from sqlalchemy import text
# ---------------------

# --- Configuration du logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Initialisation de l'application FastAPI ---
app = FastAPI(
    title="Nanshe API V2",
    openapi_url="/api/v2/openapi.json"
)
# --- Configuration des Middlewares ---
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialisation de l'Admin ---
class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        with SessionLocal() as db:
            user = db.query(User).filter(User.username == username).first()

        if user and user.is_superuser and verify_password(password, user.hashed_password):
            request.session.update({"token": "admin_logged_in", "user": user.username})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "token" in request.session

authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
admin = Admin(app, async_engine, authentication_backend=authentication_backend, base_url="/admin")
admin.add_view(UserAdmin)
admin.add_view(CourseAdmin)
admin.add_view(AITokenLogAdmin)
admin.add_view(FeedbackAdmin)
app.include_router(api_router, prefix="/api/v2")


# --- Événement de Démarrage (MODIFIÉ) ---
@app.on_event("startup")
async def startup():
    logger.info("Vérification et création des tables de la base de données...")
    async with async_engine.begin() as conn:
        # --- NOUVEAU BLOC ---
        # On s'assure que l'extension pgvector est activée
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
        # ---------------------
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Les tables de la base de données sont prêtes.")

# --- Route Racine ---
@app.get("/")
def read_root():
    return {"message": "Welcome to Nanshe API V2!"}