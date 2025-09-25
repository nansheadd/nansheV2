"""Unit tests covering the vector-store backed classifier."""

from __future__ import annotations

import pytest

from app.models.analytics.vector_store_model import VectorStore
from app.services.classification_service import DBClassifier


@pytest.fixture()
def classifier() -> DBClassifier:
    return DBClassifier()


def test_classify_returns_empty_when_embedding_is_empty(monkeypatch, db_session, classifier):
    """If the embedding provider returns an empty vector we should not query the DB."""

    monkeypatch.setattr(
        "app.services.classification_service.get_embedding", lambda _: []
    )

    assert classifier.classify("hello", db_session) == []


def test_classify_returns_top_matches_sorted_by_confidence(
    monkeypatch, db_session, classifier
):
    """Valid embeddings stored in the DB should be ranked by cosine similarity."""

    monkeypatch.setattr(
        "app.services.classification_service.get_embedding",
        lambda _: [1.0, 0.0],
    )

    entries = [
        VectorStore(
            chunk_text="Skill Alpha",
            embedding=[1.0, 0.0],
            domain="dev",
            area="python",
            skill="alpha",
            source_language="fr",
            content_type="lesson",
        ),
        VectorStore(
            chunk_text="Skill Beta",
            embedding=[0.7, 0.7],
            domain="dev",
            area="python",
            skill="beta",
            source_language="fr",
            content_type="lesson",
        ),
        VectorStore(
            chunk_text="Skill Gamma",
            embedding=[0.0, 1.0],
            domain="dev",
            area="python",
            skill="gamma",
            source_language="fr",
            content_type="lesson",
        ),
    ]

    db_session.add_all(entries)
    db_session.commit()

    results = classifier.classify("hello", db_session, top_k=2, threshold=0.1)

    assert len(results) == 2
    assert [result["category"]["name"] for result in results] == ["alpha", "beta"]
    assert results[0]["confidence"] > results[1]["confidence"]


def test_classify_filters_below_threshold_and_invalid_embeddings(
    monkeypatch, db_session, classifier
):
    """Rows with invalid vectors or low similarity should be ignored."""

    monkeypatch.setattr(
        "app.services.classification_service.get_embedding",
        lambda _: [1.0, 0.0],
    )

    db_session.add_all(
        [
            VectorStore(
                chunk_text="Valid High",
                embedding=[1.0, 0.0],
                domain="dev",
                area="python",
                skill="top",
                source_language="fr",
                content_type="lesson",
            ),
            VectorStore(
                chunk_text="Weak match",
                embedding=[0.2, 0.2],
                domain="dev",
                area="python",
                skill="weak",
                source_language="fr",
                content_type="lesson",
            ),
            # Storing a non-iterable embedding should be skipped safely.
            VectorStore(
                chunk_text="Broken",
                embedding=7,  # type: ignore[arg-type]
                domain="dev",
                area="python",
                skill="broken",
                source_language="fr",
                content_type="lesson",
            ),
        ]
    )
    db_session.commit()

    results = classifier.classify("hello", db_session, top_k=5, threshold=0.9)

    assert len(results) == 1
    match = results[0]
    assert match["category"]["name"] == "top"
    assert match["confidence"] >= 0.9
