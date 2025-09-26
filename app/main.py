import logging
import os
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Imports de l'application
from app.core.config import settings
from app.db.base_class import Base
from app.api.v2.api import api_router
from sqlalchemy import or_

from app.core.security import verify_password, get_password_hash
from app.models.user.user_model import User
from app.db.session import async_engine, SessionLocal

# Imports pour SQLAdmin
from sqladmin.authentication import AuthenticationBackend
from app.admin import (
    AITokenLogAdmin,
    AtomAdmin,
    BackOfficeAdmin,
    BadgeAdmin,
    CapsuleAdmin,
    DashboardView,
    EmailTokenAdmin,
    FeedbackAdmin,
    GranuleAdmin,
    MoleculeAdmin,
    NotificationAdmin,
    UserActivityLogAdmin,
    UserAdmin,
    UserAnswerLogAdmin,
    UserBadgeAdmin,
    UserCapsuleEnrollmentAdmin,
    UserCapsuleProgressAdmin,
)

# --- Configuration du logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Initialisation de l'application FastAPI ---
app = FastAPI(
    title="Nanshe API V2",
    openapi_url="/api/v2/openapi.json"
)
def _sanitize_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    value = origin.strip()
    if not value:
        return None
    if not value.startswith("http"):
        value = f"https://{value}"
    return value.rstrip("/")


def _compile_origin_regex(patterns: set[str]) -> re.Pattern[str] | None:
    valid_patterns: list[str] = []
    for pattern in sorted(patterns):
        candidate = pattern.strip()
        if not candidate:
            continue

        try:
            re.compile(candidate)
        except re.error as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Regex CORS ignorée (invalide): %s (%s)",
                candidate,
                exc,
            )
            continue

        valid_patterns.append(candidate)

    if not valid_patterns:
        return None

    if len(valid_patterns) == 1:
        return re.compile(valid_patterns[0])

    combined = "|".join(f"(?:{pattern})" for pattern in valid_patterns)
    return re.compile(combined)


def _build_cors_config() -> tuple[list[str], re.Pattern[str] | None]:
    base_origins = {_sanitize_origin(o) for o in settings.BACKEND_CORS_ORIGINS}

    for candidate in (
        str(settings.FRONTEND_BASE_URL),
        str(settings.BACKEND_BASE_URL),
    ):
        base_origins.add(_sanitize_origin(candidate))

    vercel_host = os.getenv("VERCEL_URL")
    base_origins.add(_sanitize_origin(vercel_host))

    additional = os.getenv("ADDITIONAL_CORS_ORIGINS")
    if additional:
        for origin in additional.split(","):
            base_origins.add(_sanitize_origin(origin))

    allow_origins = sorted({origin for origin in base_origins if origin})

    regex_candidates = {
        pattern.strip()
        for pattern in getattr(settings, "BACKEND_CORS_ORIGIN_REGEXES", [])
        if pattern and pattern.strip()
    }

    additional_regexes = os.getenv("ADDITIONAL_CORS_ORIGIN_REGEXES")
    if additional_regexes:
        for pattern in additional_regexes.split(","):
            candidate = pattern.strip()
            if candidate:
                regex_candidates.add(candidate)

    if any(origin and "vercel.app" in origin for origin in allow_origins):
        regex_candidates.add(r"^https://.*\\.vercel\\.app$")

    allow_origin_regex = _compile_origin_regex(regex_candidates)

    logger.info("CORS origins configurés: %s", allow_origins)
    if allow_origin_regex is not None:
        logger.info("CORS regex configurés: %s", allow_origin_regex.pattern)

    return allow_origins, allow_origin_regex


# --- Configuration des Middlewares ---
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

cors_origins, cors_regex = _build_cors_config()
_HTMX_HEADERS = {
    "HX-Request",
    "HX-Target",
    "HX-Trigger",
    "HX-Trigger-Name",
    "HX-Current-URL",
    "HX-History-Restore-Request",
}

cors_headers = {"Authorization", "Content-Type", "X-App-Lang"} | _HTMX_HEADERS

cors_kwargs: dict[str, object] = {
    "allow_origins": cors_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": sorted(cors_headers),
}

if cors_regex is not None:
    cors_kwargs["allow_origin_regex"] = cors_regex

app.add_middleware(CORSMiddleware, **cors_kwargs)


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
admin = BackOfficeAdmin(
    app,
    async_engine,
    authentication_backend=authentication_backend,
    base_url="/admin",
)
admin.add_view(DashboardView)
admin.add_view(UserAdmin)
admin.add_view(CapsuleAdmin)
admin.add_view(GranuleAdmin)
admin.add_view(MoleculeAdmin)
admin.add_view(AtomAdmin)
admin.add_view(UserCapsuleEnrollmentAdmin)
admin.add_view(UserCapsuleProgressAdmin)
admin.add_view(UserActivityLogAdmin)
admin.add_view(UserAnswerLogAdmin)
admin.add_view(AITokenLogAdmin)
admin.add_view(FeedbackAdmin)
admin.add_view(NotificationAdmin)
admin.add_view(EmailTokenAdmin)
admin.add_view(BadgeAdmin)
admin.add_view(UserBadgeAdmin)
app.include_router(api_router, prefix="/api/v2")


# --- Événement de Démarrage (MODIFIÉ) ---
@app.on_event("startup")
async def startup():
    logger.info("Vérification et création des tables de la base de données...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Les tables de la base de données sont prêtes.")

    # --- Création de l'administrateur par défaut ---
    default_admin_identifier = "nanshe@admin.com"
    default_admin_password = "password"

    with SessionLocal() as session:
        admin_user = session.query(User).filter(
            or_(
                User.email == default_admin_identifier,
                User.username == default_admin_identifier,
            )
        ).first()

        if admin_user is None:
            logger.info("Création de l'administrateur par défaut '%s'.", default_admin_identifier)
            admin_user = User(
                username=default_admin_identifier,
                email=default_admin_identifier,
                hashed_password=get_password_hash(default_admin_password),
                is_superuser=True,
                is_active=True,
                is_email_verified=True,
            )
            session.add(admin_user)
            session.commit()
            logger.info("✅ Administrateur par défaut créé.")
        else:
            logger.info("Administrateur par défaut déjà présent.")

# --- Route Racine ---
@app.get("/")
def read_root():
    return {"message": "Welcome to Nanshe API V2!"}
