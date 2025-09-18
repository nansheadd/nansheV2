from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BadgeRead(BaseModel):
    id: int
    name: str
    description: str
    icon: Optional[str]
    category: str
    points: int
    slug: str

    class Config:
        from_attributes = True


class BadgeWithStatus(BaseModel):
    badge: BadgeRead
    is_unlocked: bool
    awarded_at: Optional[datetime]
