# Fichier: nanshe/backend/app/api/v2/api.py (CORRIGÉ)
from fastapi import APIRouter
from .endpoints import (
    user_router,
    progress_router,
    toolbox_router,
    feedback_router,
    nlp_router,
    capsule_router,
    notification_router,
    badge_router,
    notification_ws,
    programming_router,
    stripe_router,
    ws_debug,
    auth_email_router,
    resend_webhook_router,
    legal_router,
    conversation_ws,
    feature_vote_router,
    chat_router,
    learning_router,
    journal_router,
    srs_router,
)

api_router = APIRouter()

api_router.include_router(user_router.router, prefix="/users", tags=["Users"])
api_router.include_router(progress_router.router, prefix="/progress", tags=["Progress"])
api_router.include_router(toolbox_router.router, prefix="/toolbox", tags=["Toolbox"])
api_router.include_router(journal_router.router, prefix="/journal", tags=["Journal"])
api_router.include_router(learning_router.router, prefix="/learning", tags=["Learning"])
api_router.include_router(srs_router.router, prefix="/srs", tags=["Learning"])
api_router.include_router(feedback_router.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(nlp_router.router, prefix="/nlp", tags=["Nlp"])
api_router.include_router(capsule_router.router, prefix="/capsules", tags=["Capsule"])
api_router.include_router(notification_router.router, prefix="/notifications", tags=["Notifications"])
api_router.include_router(notification_ws.router, tags=["Notifications"])
api_router.include_router(conversation_ws.router, tags=["Conversations"])
api_router.include_router(chat_router.router, prefix="/chat", tags=["Chat"])
api_router.include_router(ws_debug.router,prefix="/ws-test", tags=["WsDebug"])
api_router.include_router(badge_router.router, prefix="/badges", tags=["Badges"])
api_router.include_router(programming_router.router, prefix="/programming", tags=["Programming"])
api_router.include_router(stripe_router.router, prefix="/stripe", tags=["stripe"])
api_router.include_router(auth_email_router.router, prefix="/auth", tags=["Auth Email"])
api_router.include_router(resend_webhook_router.router, tags=["Webhooks"])
api_router.include_router(legal_router.router)
api_router.include_router(feature_vote_router.router, prefix="/feature-polls", tags=["FeatureVotes"])
api_router.include_router(feature_vote_router.router, prefix="/feature-votes", tags=["FeatureVotes"])
