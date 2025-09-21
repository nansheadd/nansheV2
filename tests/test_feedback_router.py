from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.v2.endpoints.feedback_router import submit_feedback, get_feedback_statuses
from app.schemas.analytics.feedback_schema import FeedbackIn, BulkFeedbackStatusIn
from app.models.analytics.feedback_model import ContentFeedback
from tests.utils import create_user


@pytest.fixture()
def user(db_session):
    return create_user(db_session, username="tester", email="tester@example.com")


def test_submit_like_feedback(db_session, user):
    payload = FeedbackIn(content_type="atom", content_id=42, rating="liked")
    result = submit_feedback(payload, db=db_session, current_user=user)
    assert result["rating"] == "liked"
    assert result["reason_code"] is None
    assert db_session.query(ContentFeedback).count() == 1


def test_submit_dislike_requires_reason(db_session, user):
    payload = FeedbackIn(content_type="atom", content_id=10, rating="disliked")
    with pytest.raises(HTTPException) as exc:
        submit_feedback(payload, db=db_session, current_user=user)
    assert exc.value.status_code == 400
    assert exc.value.detail == "reason_required"


def test_submit_dislike_with_reason(db_session, user):
    payload = FeedbackIn(
        content_type="atom",
        content_id=55,
        rating="disliked",
        reason_code="incorrect",
        comment="la correction est fausse",
    )
    result = submit_feedback(payload, db=db_session, current_user=user)
    assert result["rating"] == "disliked"
    assert result["reason_code"] == "incorrect"
    assert "fausse" in result["comment"]

    payload = FeedbackIn(content_type="atom", content_id=55, rating="liked")
    result = submit_feedback(payload, db=db_session, current_user=user)
    assert result["rating"] == "liked"
    assert result["reason_code"] is None


def test_remove_feedback(db_session, user):
    submit_feedback(FeedbackIn(content_type="molecule", content_id=7, rating="liked"), db=db_session, current_user=user)

    result = submit_feedback(
        FeedbackIn(content_type="molecule", content_id=7, rating="none"),
        db=db_session,
        current_user=user,
    )
    assert result["status"] == "deleted"
    assert db_session.query(ContentFeedback).count() == 0


def test_get_feedback_statuses(db_session, user):
    submit_feedback(FeedbackIn(content_type="atom", content_id=1, rating="liked"), db=db_session, current_user=user)
    submit_feedback(
        FeedbackIn(content_type="atom", content_id=2, rating="disliked", reason_code="other", comment="meh"),
        db=db_session,
        current_user=user,
    )

    payload = BulkFeedbackStatusIn(content_type="atom", content_ids=[1, 2, 3])
    result = get_feedback_statuses(payload, db=db_session, current_user=user)
    assert result["statuses"] == {1: "liked", 2: "disliked"}
