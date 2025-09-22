"""Routes publiques pour la classification NLP légère."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.nlp.topic_classifier import TopicClassifier

router = APIRouter(prefix="/nlp", tags=["nlp"])
if getattr(router, "state", None) is None:
    router.state = SimpleNamespace()
logger = logging.getLogger(__name__)


@router.on_event("startup")
def _init_classifier() -> None:
    if getattr(router.state, "classifier", None):
        return

    base_path = Path(__file__).resolve().parents[3]
    train_path = base_path / "core" / "course_topic_train.jsonl"
    labels_path = base_path / "core" / "course_topic_labels.json"

    try:
        classifier = TopicClassifier(str(train_path), str(labels_path))
        router.state.classifier = classifier
        logger.info("TopicClassifier initialisé avec %s labels.", len(classifier.label_set))
    except Exception as exc:  # pragma: no cover - dépend des fichiers de données
        logger.error("Impossible d'initialiser le TopicClassifier: %s", exc)
        router.state.classifier = None


def get_classifier() -> TopicClassifier:
    classifier = getattr(router.state, "classifier", None)
    if not classifier:
        raise HTTPException(status_code=503, detail="Classifier not initialized")
    return classifier


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
        "scores": scores,
    }


@router.post("/rebuild-centroids")
def rebuild_centroids(clf: TopicClassifier = Depends(get_classifier)):
    clf.rebuild()
    return {"status": "ok"}
