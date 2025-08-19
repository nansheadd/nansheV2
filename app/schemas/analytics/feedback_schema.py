# Fichier: nanshe/backend/app/schemas/analytics/feedback_schema.py

from pydantic import BaseModel, Field
from typing import List, Dict, Annotated

# Le schéma pour envoyer un feedback
class FeedbackIn(BaseModel):
    content_type: str
    content_id: int
    rating: Annotated[str, Field(pattern=r'^(liked|disliked)$')]

# Le schéma pour demander le statut de plusieurs feedbacks
class BulkFeedbackStatusIn(BaseModel):
    content_type: str
    content_ids: List[int]

# Le schéma pour recevoir le statut de plusieurs feedbacks
class BulkFeedbackStatusOut(BaseModel):
    statuses: Dict[int, str]