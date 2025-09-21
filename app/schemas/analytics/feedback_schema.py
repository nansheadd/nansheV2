# Fichier: nanshe/backend/app/schemas/analytics/feedback_schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Annotated, Optional

# Le schéma pour envoyer un feedback
class FeedbackIn(BaseModel):
    content_type: str
    content_id: int
    rating: Annotated[str, Field(pattern=r'^(liked|disliked|none)$')]
    reason_code: Optional[str] = None
    comment: Optional[str] = None

# Le schéma pour demander le statut de plusieurs feedbacks
class BulkFeedbackStatusIn(BaseModel):
    content_type: str
    content_ids: List[int]

# Le schéma pour recevoir le statut de plusieurs feedbacks
class BulkFeedbackStatusOut(BaseModel):
    statuses: Dict[int, str]


class FeedbackOut(BaseModel):
    id: Optional[int]
    rating: Optional[str]
    status: Optional[str]
    reason_code: Optional[str] = None
    comment: Optional[str] = None
