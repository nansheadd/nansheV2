from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Mapping

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user.user_model import SubscriptionStatus, User
from app.models.vote.feature_vote_model import FeaturePoll, FeaturePollOption, FeaturePollVote


@dataclass(slots=True)
class FeatureVoteError(Exception):
    """Domain-specific exception raised when vote submissions fail validation."""

    code: str
    status_code: int = 400

    def __str__(self) -> str:  # pragma: no cover - human readable message
        return self.code


class FeatureVoteService:
    """Business logic for feature voting polls."""

    MIN_ACCOUNT_AGE_DAYS = 14

    def __init__(self, db: Session, user: User | None):
        self.db = db
        self.user = user

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_active_poll(self) -> FeaturePoll | None:
        """Return the currently active poll or ``None`` if nothing is open."""
        now = self._utcnow()
        return (
            self.db.query(FeaturePoll)
            .filter(FeaturePoll.is_active.is_(True))
            .filter(or_(FeaturePoll.starts_at.is_(None), FeaturePoll.starts_at <= now))
            .filter(or_(FeaturePoll.ends_at.is_(None), FeaturePoll.ends_at >= now))
            .order_by(FeaturePoll.starts_at.asc(), FeaturePoll.id.asc())
            .first()
        )

    def submit_votes(self, poll_id: int, allocations: Mapping[int, int]) -> FeaturePoll:
        """Persist the user's votes for the given poll."""
        if not self.user:
            raise FeatureVoteError("authentication_required", status_code=401)

        poll = self.db.get(FeaturePoll, poll_id)
        if not poll:
            raise FeatureVoteError("poll_not_found", status_code=404)

        now = self._utcnow()
        if not self._is_poll_open(poll, now):
            raise FeatureVoteError("poll_closed", status_code=403)

        if not self._is_account_old_enough(reference=now):
            raise FeatureVoteError("account_too_new", status_code=403)

        cleaned_allocations: Dict[int, int] = {}
        for option_id, votes in allocations.items():
            if votes < 0:
                raise FeatureVoteError("invalid_vote_amount")
            cleaned_allocations[int(option_id)] = int(votes)

        total_requested = sum(v for v in cleaned_allocations.values() if v > 0)
        allowed_votes = self._allowed_votes(poll)
        if total_requested > allowed_votes:
            raise FeatureVoteError("vote_limit_exceeded")

        valid_option_ids = {
            row.id
            for row in (
                self.db.query(FeaturePollOption.id)
                .filter(
                    FeaturePollOption.poll_id == poll.id,
                    FeaturePollOption.is_active.is_(True),
                )
                .all()
            )
        }
        invalid_ids = set(cleaned_allocations) - valid_option_ids
        if invalid_ids:
            raise FeatureVoteError("invalid_option")

        existing_votes = {
            vote.option_id: vote
            for vote in (
                self.db.query(FeaturePollVote)
                .filter(
                    FeaturePollVote.poll_id == poll.id,
                    FeaturePollVote.user_id == self.user.id,
                )
                .all()
            )
        }

        for option_id, vote in existing_votes.items():
            new_value = cleaned_allocations.get(option_id, 0)
            if new_value <= 0:
                self.db.delete(vote)
            else:
                vote.votes = new_value
                vote.updated_at = now

        for option_id, amount in cleaned_allocations.items():
            if amount <= 0 or option_id in existing_votes:
                continue
            self.db.add(
                FeaturePollVote(
                    poll_id=poll.id,
                    option_id=option_id,
                    user_id=self.user.id,
                    votes=amount,
                    updated_at=now,
                )
            )

        self.db.commit()
        self.db.refresh(poll)
        return poll

    def build_poll_payload(self, poll: FeaturePoll) -> dict:
        """Serialize a poll along with aggregated vote data for API responses."""
        options = (
            self.db.query(FeaturePollOption)
            .filter(
                FeaturePollOption.poll_id == poll.id,
                FeaturePollOption.is_active.is_(True),
            )
            .order_by(FeaturePollOption.position.asc(), FeaturePollOption.id.asc())
            .all()
        )
        option_ids = [option.id for option in options]

        total_votes_by_option: Dict[int, int] = {option_id: 0 for option_id in option_ids}
        if option_ids:
            for option_id, total_votes in (
                self.db.execute(
                    select(FeaturePollVote.option_id, func.coalesce(func.sum(FeaturePollVote.votes), 0))
                    .where(FeaturePollVote.poll_id == poll.id)
                    .where(FeaturePollVote.option_id.in_(option_ids))
                    .group_by(FeaturePollVote.option_id)
                )
            ):
                total_votes_by_option[int(option_id)] = int(total_votes)

        user_votes_by_option: Dict[int, int] = {option_id: 0 for option_id in option_ids}
        if self.user:
            for option_id, votes in (
                self.db.execute(
                    select(FeaturePollVote.option_id, FeaturePollVote.votes)
                    .where(FeaturePollVote.poll_id == poll.id)
                    .where(FeaturePollVote.user_id == self.user.id)
                )
            ):
                user_votes_by_option[int(option_id)] = int(votes)

        total_user_votes = sum(user_votes_by_option.values())
        allowed_votes = self._allowed_votes(poll)
        now = self._utcnow()
        can_vote = self._can_user_vote(poll, reference=now)
        remaining_votes = max(0, allowed_votes - total_user_votes) if can_vote else 0
        account_age_days = self._account_age_days(reference=now)

        options_payload = [
            {
                "id": option.id,
                "title": option.title,
                "description": option.description,
                "position": option.position,
                "vote_count": total_votes_by_option.get(option.id, 0),
                "user_votes": user_votes_by_option.get(option.id, 0),
            }
            for option in options
        ]

        return {
            "id": poll.id,
            "slug": poll.slug,
            "title": poll.title,
            "description": poll.description,
            "starts_at": poll.starts_at,
            "ends_at": poll.ends_at,
            "is_active": poll.is_active,
            "max_votes_free": poll.max_votes_free,
            "max_votes_premium": poll.max_votes_premium,
            "options": options_payload,
            "user_total_votes": total_user_votes,
            "user_remaining_votes": remaining_votes,
            "user_allowed_votes": allowed_votes,
            "user_can_vote": can_vote,
            "min_account_age_days": self.MIN_ACCOUNT_AGE_DAYS,
            "account_age_days": account_age_days,
            "total_votes_cast": sum(total_votes_by_option.values()),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _account_age_days(self, *, reference: datetime | None = None) -> int | None:
        if not self.user or not self.user.created_at:
            return None
        created_at = self._normalize_datetime(self.user.created_at)
        reference = reference or self._utcnow()
        delta = reference - created_at
        if delta.total_seconds() < 0:
            return 0
        return delta.days

    def _is_account_old_enough(self, *, reference: datetime | None = None) -> bool:
        age_days = self._account_age_days(reference=reference)
        if age_days is None:
            return False
        return age_days >= self.MIN_ACCOUNT_AGE_DAYS

    def _allowed_votes(self, poll: FeaturePoll) -> int:
        if not self.user:
            return poll.max_votes_free
        if self.user.subscription_status == SubscriptionStatus.PREMIUM:
            return poll.max_votes_premium
        return poll.max_votes_free

    def _is_poll_open(self, poll: FeaturePoll, now: datetime | None = None) -> bool:
        if not poll.is_active:
            return False
        now = now or self._utcnow()
        start = self._normalize_datetime(poll.starts_at)
        end = self._normalize_datetime(poll.ends_at)
        if start and now < start:
            return False
        if end and now > end:
            return False
        return True

    def _can_user_vote(self, poll: FeaturePoll, *, reference: datetime | None = None) -> bool:
        if not self.user:
            return False
        if not self._is_poll_open(poll, reference):
            return False
        return self._is_account_old_enough(reference=reference)
