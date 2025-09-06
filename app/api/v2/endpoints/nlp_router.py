# app/api/routers/nlp.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.core.config import settings
from app.nlp.topic_classifier import TopicClassifier

router = APIRouter(prefix="/nlp", tags=["nlp"])

# Singleton global chargé au boot (voir main.py plus bas)
_classifier: TopicClassifier | None = None

def get_classifier() -> TopicClassifier:
    if not router.state.__dict__.get("classifier"):
        raise HTTPException(status_code=503, detail="Classifier not initialized")
    return router.state.classifier

class ClassifyIn(BaseModel):
    text: str

@router.post("/classify-topic")
def classify_topic(payload: ClassifyIn, clf: TopicClassifier = Depends(get_classifier)):
    label, score, scores = clf.predict(payload.text)
    second = scores[1][1] if len(scores) > 1 else 0.0
    margin = score - second
    return {
        "label": label,
        "score": score,
        "second_best": scores[1][0] if len(scores) > 1 else None,
        "margin": margin,
        "scores": scores  # utile pour debug UI
    }

@router.post("/rebuild-centroids")
def rebuild_centroids(clf: TopicClassifier = Depends(get_classifier)):
    clf.rebuild()
    return {"status": "ok"}
