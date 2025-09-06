# app/nlp/topic_classifier.py
import json
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
from sentence_transformers import SentenceTransformer

class TopicClassifier:
    def __init__(self, train_path: str, labels_path: str, model_name: str = "all-MiniLM-L6-v2"):
        self.train_path = train_path
        self.labels_path = labels_path
        self.model = SentenceTransformer(model_name)
        self.labels_desc: Dict[str, str] = json.loads(Path(labels_path).read_text(encoding="utf-8"))
        self.train: List[Dict] = [json.loads(l) for l in Path(train_path).read_text(encoding="utf-8").splitlines()]
        self.label_set = sorted(set(row["label"] for row in self.train))
        self.centroids: Dict[str, np.ndarray] = {}
        self._build_centroids()

    def _build_centroids(self):
        texts = [row["text"] for row in self.train]
        labels = [row["label"] for row in self.train]
        embs = self.model.encode(texts, normalize_embeddings=True)

        by_label: Dict[str, List[np.ndarray]] = {lab: [] for lab in self.label_set}
        for e, lab in zip(embs, labels):
            by_label[lab].append(e)

        self.centroids = {lab: np.mean(np.stack(vecs, axis=0), axis=0) for lab, vecs in by_label.items() if vecs}

    def predict(self, text: str) -> Tuple[str, float, List[Tuple[str,float]]]:
        if not text or not text.strip():
            return "general", 0.0, []
        q = self.model.encode([text], normalize_embeddings=True)[0]
        scores = []
        for lab, c in self.centroids.items():
            score = float(np.dot(q, c))  # cosinus car normalisés
            scores.append((lab, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        best_label, best_score = scores[0]
        return best_label, best_score, scores

    def rebuild(self):
        # recharger fichiers (au cas où tu as ajouté des exemples)
        self.labels_desc = json.loads(Path(self.labels_path).read_text(encoding="utf-8"))
        self.train = [json.loads(l) for l in Path(self.train_path).read_text(encoding="utf-8").splitlines()]
        self.label_set = sorted(set(row["label"] for row in self.train))
        self._build_centroids()
