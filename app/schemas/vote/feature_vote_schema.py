from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VoteAllocation(BaseModel):
    option_id: int = Field(..., ge=1)
    votes: int = Field(..., ge=0)


class FeaturePollVoteIn(BaseModel):
    allocations: List[VoteAllocation]

    @model_validator(mode="after")
    def _ensure_unique_option(self) -> "FeaturePollVoteIn":
        seen: set[int] = set()
        for allocation in self.allocations:
            if allocation.option_id in seen:
                raise ValueError("duplicate_option")
            seen.add(allocation.option_id)
        return self


class FeaturePollOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    position: int
    vote_count: int
    user_votes: int


class FeaturePollOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    is_active: bool
    max_votes_free: int
    max_votes_premium: int
    options: List[FeaturePollOptionOut]
    user_total_votes: int
    user_remaining_votes: int
    user_allowed_votes: int
    user_can_vote: bool
    min_account_age_days: int
    account_age_days: Optional[int]
    total_votes_cast: int
