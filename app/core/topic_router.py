# app/core/topic_router.py  (nouveau module)
from .config import settings
from app.nlp.topic_classifier import TopicClassifier

# Singleton au boot FastAPI
TRAIN_PATH ="course_topic_train.jsonl"
LABELS_PATH = "course_topic_labels.json"
_classifier = TopicClassifier(TRAIN_PATH, LABELS_PATH)

def classify_course_topic_nlp(title: str, threshold: float = 0.35) -> str:
    label, score, scores = _classifier.predict(title)
    # marge/second-best utile si tu veux raffiner
    second_score = scores[1][1] if len(scores) > 1 else 0.0
    margin = score - second_score
    if score < threshold or margin < 0.05:
        return "general"
    return label
