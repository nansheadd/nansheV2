# Fichier: nanshe/backend/app/api/v2/api.py
from fastapi import APIRouter
from .endpoints import user_router

api_router = APIRouter()
api_router.include_router(user_router.router, tags=["users"])