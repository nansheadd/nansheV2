# Fichier: nanshe/backend/app/api/v2/api.py (CORRIGÉ)
from fastapi import APIRouter
from .endpoints import user_router, course_router, level_router, progress_router, chapter_router, toolbox_router, feedback_router,knowledge_node_router

api_router = APIRouter()

api_router.include_router(user_router.router, prefix="/users", tags=["Users"])
api_router.include_router(course_router.router, prefix="/courses", tags=["Courses"])
api_router.include_router(level_router.router, prefix="/levels", tags=["Levels"])
api_router.include_router(chapter_router.router, prefix="/chapters", tags=["Chapters"]) 
api_router.include_router(progress_router.router, prefix="/progress", tags=["Progress"])
api_router.include_router(toolbox_router.router, prefix="/toolbox", tags=["Toolbox"])
api_router.include_router(feedback_router.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(knowledge_node_router.router, prefix="/nodes", tags=["nodes"])
api_router.include_router(knowledge_node_router.router, prefix="/knowledge-nodes", tags=["Knowledge Nodes"])

