from datetime import datetime, timedelta

import pytest

from app.models.user.user_model import SubscriptionStatus
from app.services.feature_vote_service import FeatureVoteError, FeatureVoteService
from tests.utils import create_feature_poll, create_user


def _days_ago(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def test_vote_requires_account_age(db_session):
    poll = create_feature_poll(db_session, slug="poll-young")
    user = create_user(db_session, username="young", email="young@example.com", created_at=_days_ago(5))

    service = FeatureVoteService(db_session, user)
    option_id = poll.options[0].id

    with pytest.raises(FeatureVoteError) as exc:
        service.submit_votes(poll.id, {option_id: 1})
    assert exc.value.code == "account_too_new"
    assert exc.value.status_code == 403

    payload = service.build_poll_payload(poll)
    assert payload["user_can_vote"] is False
    assert payload["user_remaining_votes"] == 0
    assert payload["user_allowed_votes"] == poll.max_votes_free
    assert payload["account_age_days"] == 5


def test_free_user_vote_limit_and_reallocation(db_session):
    poll = create_feature_poll(db_session, slug="poll-free")
    user = create_user(db_session, username="free", email="free@example.com", created_at=_days_ago(30))

    service = FeatureVoteService(db_session, user)
    option_a = poll.options[0].id
    option_b = poll.options[1].id

    poll_after = service.submit_votes(poll.id, {option_a: 1})
    payload = service.build_poll_payload(poll_after)
    assert payload["user_total_votes"] == 1
    assert payload["user_remaining_votes"] == 0
    assert payload["options"][0]["vote_count"] == 1

    with pytest.raises(FeatureVoteError) as exc:
        service.submit_votes(poll.id, {option_a: 2})
    assert exc.value.code == "vote_limit_exceeded"

    poll_after = service.submit_votes(poll.id, {option_b: 1})
    payload = service.build_poll_payload(poll_after)
    assert payload["options"][0]["vote_count"] == 0
    assert payload["options"][1]["vote_count"] == 1

    poll_after = service.submit_votes(poll.id, {})
    payload = service.build_poll_payload(poll_after)
    assert payload["user_total_votes"] == 0
    assert payload["total_votes_cast"] == 0


def test_premium_user_can_cast_three_votes(db_session):
    poll = create_feature_poll(db_session, slug="poll-premium")
    free_user = create_user(db_session, username="free2", email="free2@example.com", created_at=_days_ago(40))
    premium_user = create_user(
        db_session,
        username="premium",
        email="premium@example.com",
        created_at=_days_ago(60),
        subscription_status=SubscriptionStatus.PREMIUM,
    )

    free_service = FeatureVoteService(db_session, free_user)
    premium_service = FeatureVoteService(db_session, premium_user)

    option_a = poll.options[0].id
    option_b = poll.options[1].id

    free_service.submit_votes(poll.id, {option_a: 1})
    poll_after = premium_service.submit_votes(poll.id, {option_a: 2, option_b: 1})

    payload = premium_service.build_poll_payload(poll_after)
    assert payload["user_total_votes"] == 3
    assert payload["user_remaining_votes"] == 0
    assert payload["options"][0]["vote_count"] == 3  # 1 free + 2 premium
    assert payload["options"][1]["vote_count"] == 1
    assert payload["total_votes_cast"] == 4

    with pytest.raises(FeatureVoteError):
        premium_service.submit_votes(poll.id, {option_a: 3, option_b: 1})


def test_get_active_poll_respects_schedule(db_session):
    future_start = datetime.utcnow() + timedelta(days=1)
    create_feature_poll(
        db_session,
        slug="poll-future",
        starts_at=future_start,
    )
    active_poll = create_feature_poll(
        db_session,
        slug="poll-current",
        starts_at=datetime.utcnow() - timedelta(days=1),
        ends_at=datetime.utcnow() + timedelta(days=1),
    )

    user = create_user(db_session, username="viewer", email="viewer@example.com", created_at=_days_ago(20))
    service = FeatureVoteService(db_session, user)

    fetched = service.get_active_poll()
    assert fetched is not None
    assert fetched.id == active_poll.id
