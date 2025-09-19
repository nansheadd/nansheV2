from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime
from app.db.base_class import Base

class EmailEvent(Base):
    __tablename__ = "email_events"

    id = Column(Integer, primary_key=True)
    message_id = Column(String(100), index=True)
    to = Column(String(255))
    subject = Column(String(255))
    status = Column(String(50))  # delivered, bounced, complained, etc.
    event_type = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    payload = Column(JSON)  # raw webhook data