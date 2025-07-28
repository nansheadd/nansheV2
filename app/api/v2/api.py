# Fichier: nanshe/backend/app/api/v2/api.py (CORRIGÉ)
from fastapi import APIRouter
from .endpoints import user_router, course_router, level_router, progress_router

api_router = APIRouter()

api_router.include_router(user_router.router, prefix="/users", tags=["Users"])
api_router.include_router(course_router.router, prefix="/courses", tags=["Courses"])
api_router.include_router(level_router.router, prefix="/courses", tags=["Levels"])
api_router.include_router(progress_router.router, prefix="/progress", tags=["Progress"])