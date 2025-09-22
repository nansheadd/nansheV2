"""Pydantic models used by the conversation websocket backend."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class ConversationScope(str, Enum):
    """Different scopes supported by the conversation service."""

    GENERAL = "general"
    DOMAIN = "domain"


class ChannelDescriptor(BaseModel):
    """Represents a logical conversation channel."""

    scope: ConversationScope
    domain: str | None = Field(default=None, description="Salon or domain identifier")
    area: str | None = Field(default=None, description="Optional area tag inside the domain")

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    @classmethod
    def from_params(
        cls, *, domain: str | None = None, area: str | None = None
    ) -> "ChannelDescriptor":
        """Build a channel descriptor from optional request parameters."""

        normalized_domain = _normalize_identifier(domain)
        normalized_area = _normalize_identifier(area)

        # "general" (or blank) is treated as the global room
        if normalized_domain in {None, "general"}:
            normalized_domain = None
            scope = ConversationScope.GENERAL
        else:
            scope = ConversationScope.DOMAIN

        return cls(scope=scope, domain=normalized_domain, area=normalized_area)

    @property
    def key(self) -> str:
        """Stable key used to store channel specific state."""

        domain_part = (self.domain or "general").lower()
        area_part = (self.area or "*").lower()
        return f"{self.scope}:{domain_part}:{area_part}"

    def payload(self) -> Dict[str, Any]:
        """Serializable representation used when notifying clients."""

        return {
            "scope": self.scope.value,
            "domain": self.domain,
            "area": self.area,
            "key": self.key,
        }


def _normalize_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


class UserPublicInfo(BaseModel):
    """Subset of user information exposed over the websocket."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str | None = None
    active_title: str | None = None
    profile_border_color: str | None = None
    level: int | None = None
    xp_points: int | None = None


class MessageOptions(BaseModel):
    """Options that control message presentation and counters."""

    citation_count: int = Field(default=0, ge=0)
    reply_count: int = Field(default=0, ge=0)
    allow_comments: bool = Field(default=True)
    extra: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class ConversationMessage(BaseModel):
    """Canonical representation of a conversation message."""

    model_config = ConfigDict(extra="allow", frozen=True, use_enum_values=True)

    id: str
    scope: ConversationScope
    domain: str | None = None
    area: str | None = None
    content: str
    created_at: datetime
    user: UserPublicInfo
    options: MessageOptions = Field(default_factory=MessageOptions)
