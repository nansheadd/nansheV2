"""Topic classifier based on lightweight hashing embeddings."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from app.core.embeddings import (
    EMBEDDING_DIMENSION,
    cosine_similarity,
    get_text_embedding,
    normalize_vector,
)

logger = logging.getLogger(__name__)


class TopicClassifier:
    def __init__(self, train_path: str, labels_path: str):
        self.train_path = train_path
        self.labels_path = labels_path
        self.labels_desc: Dict[str, str] = {}
        self.train: List[Dict] = []
        self.label_set: List[str] = []
        self.centroids: Dict[str, List[float]] = {}
        self._load_data()
        self._build_centroids()

    def _load_data(self) -> None:
        self.labels_desc = json.loads(Path(self.labels_path).read_text(encoding="utf-8"))
        self.train = [
            json.loads(line)
            for line in Path(self.train_path).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.label_set = sorted({row["label"] for row in self.train if "label" in row})
        logger.info("TopicClassifier chargé avec %s exemples.", len(self.train))

    def _build_centroids(self) -> None:
        if not self.train:
            self.centroids = {}
            return

        accumulator: Dict[str, List[float]] = {
            label: [0.0] * EMBEDDING_DIMENSION for label in self.label_set
        }
        counts = defaultdict(int)

        for row in self.train:
            text = row.get("text", "")
            label = row.get("label")
            if not text or not label:
                continue

            embedding = normalize_vector(get_text_embedding(text, allow_remote=False))
            counts[label] += 1
            bucket = accumulator[label]
            for idx, value in enumerate(embedding):
                bucket[idx] += value

        centroids: Dict[str, List[float]] = {}
        for label, summed in accumulator.items():
            if not counts[label]:
                continue
            averaged = [value / counts[label] for value in summed]
            centroids[label] = normalize_vector(averaged)

        self.centroids = centroids
        logger.info("TopicClassifier centroids calculés pour %s labels.", len(self.centroids))

    def predict(self, text: str) -> Tuple[str, float, List[Tuple[str, float]]]:
        if not text or not text.strip() or not self.centroids:
            return "general", 0.0, []

        query_embedding = normalize_vector(get_text_embedding(text, allow_remote=False))
        scores: List[Tuple[str, float]] = []
        for label, centroid in self.centroids.items():
            score = cosine_similarity(query_embedding, centroid)
            scores.append((label, score))
        scores.sort(key=lambda item: item[1], reverse=True)

        best_label, best_score = scores[0]
        return best_label, best_score, scores

    def rebuild(self) -> None:
        self._load_data()
        self._build_centroids()
