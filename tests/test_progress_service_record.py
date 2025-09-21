from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.services.progress_service import ProgressService, calculate_capsule_xp_distribution
from app.models.capsule.utility_models import UserCapsuleProgress
from app.models.progress.user_activity_log_model import UserActivityLog
from tests.utils import create_user, create_capsule_graph


def test_record_atom_completion_awards_once(db_session):
    user = create_user(db_session, username="learner", email="learner@example.com")
    capsule, molecule, lesson_atom, quiz_atom = create_capsule_graph(db_session, user.id)

    expected_atom_xp, _ = calculate_capsule_xp_distribution(capsule)

    service = ProgressService(db=db_session, user_id=user.id)

    progress = service.record_atom_completion(lesson_atom.id)
    first_gain = progress.xp
    assert first_gain == expected_atom_xp[lesson_atom.id]

    progress = service.record_atom_completion(lesson_atom.id)
    assert progress.xp == first_gain

    progress = service.record_atom_completion(quiz_atom.id)
    assert progress.xp == expected_atom_xp[lesson_atom.id] + expected_atom_xp[quiz_atom.id]
    assert progress.xp <= 60000


def test_record_atom_completion_creates_progress_entries(db_session):
    user = create_user(db_session, username="learner", email="learner@example.com")
    capsule, molecule, lesson_atom, _ = create_capsule_graph(db_session, user.id)

    service = ProgressService(db=db_session, user_id=user.id)
    progress = service.record_atom_completion(lesson_atom.id)

    assert progress.user_id == user.id
    assert progress.capsule_id == capsule.id
    assert progress.xp > 0

    capsule_progress = (
        db_session.query(UserCapsuleProgress)
        .filter_by(user_id=user.id, capsule_id=capsule.id)
        .first()
    )
    assert capsule_progress is not None
    assert capsule_progress.xp == progress.xp


def test_get_user_stats_breakdown(db_session):
    user = create_user(db_session, username="tracker", email="tracker@example.com")
    capsule, molecule, lesson_atom, _ = create_capsule_graph(db_session, user.id)

    log = UserActivityLog(
        user_id=user.id,
        capsule_id=capsule.id,
        atom_id=lesson_atom.id,
        start_time=datetime.utcnow() - timedelta(minutes=45),
        end_time=datetime.utcnow() - timedelta(minutes=15),
    )
    db_session.add(log)
    db_session.commit()

    service = ProgressService(db=db_session, user_id=user.id)
    stats = service.get_user_stats()

    assert stats["total_study_time_seconds"] >= 1800
    assert stats["current_streak_days"] >= 1
    assert stats["total_sessions"] >= 1
    assert stats["breakdown"]["by_domain"], "Expected domain breakdown to be populated"
    assert stats["breakdown"]["by_domain"][0]["domain"] == capsule.domain
