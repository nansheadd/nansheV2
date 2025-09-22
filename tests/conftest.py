"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base_class import Base
from app.models.analytics.feedback_model import (
    ContentFeedback,
    ContentFeedbackDetail,
)
from app.models.analytics.classification_feedback_model import ClassificationFeedback
from app.models.capsule.atom_model import Atom
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.language_roadmap_model import Skill
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.utility_models import UserCapsuleEnrollment, UserCapsuleProgress
from app.models.user.user_model import User
from app.models.user.notification_model import Notification
from app.models.user.badge_model import Badge, UserBadge
from app.models.progress.user_activity_log_model import UserActivityLog
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.progress.user_atomic_progress import UserAtomProgress
from app.models.progress.user_course_progress_model import UserCourseProgress
from app.models.toolbox.coach_energy_model import CoachEnergyWallet


# Ensure the backend/app package is importable when tests run from the repo root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.append(str(BACKEND_ROOT))


TABLES = [
    User.__table__,
    Capsule.__table__,
    Granule.__table__,
    Molecule.__table__,
    Atom.__table__,
    Skill.__table__,
    UserCapsuleEnrollment.__table__,
    UserCapsuleProgress.__table__,
    UserCourseProgress.__table__,
    UserActivityLog.__table__,
    UserAnswerLog.__table__,
    UserAtomProgress.__table__,
    ContentFeedback.__table__,
    ContentFeedbackDetail.__table__,
    CoachEnergyWallet.__table__,
    Notification.__table__,
    Badge.__table__,
    UserBadge.__table__,
]


@pytest.fixture()
def engine():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine, tables=TABLES)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine, tables=TABLES)
        engine.dispose()


@pytest.fixture()
def db_session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
