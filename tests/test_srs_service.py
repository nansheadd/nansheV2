from datetime import datetime, timedelta

from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.progress.user_atomic_progress import UserAtomProgress
from app.models.progress.user_molecule_review_model import UserMoleculeReview
from app.models.user.user_model import SubscriptionStatus
from app.services.srs_service import SRSService
from tests.utils import create_capsule_graph, create_user


def test_srs_overview_and_error_journal(db_session):
    user = create_user(
        db_session,
        username="srs-user",
        email="srs@example.com",
        subscription_status=SubscriptionStatus.PREMIUM,
    )
    capsule, molecule, lesson_atom, _ = create_capsule_graph(db_session, user.id)

    progress_entry = UserAtomProgress(
        user_id=user.id,
        atom_id=lesson_atom.id,
        reset_count=1,
    )
    db_session.add(progress_entry)

    error_log = UserAnswerLog(
        user_id=user.id,
        atom_id=lesson_atom.id,
        is_correct=False,
        user_answer_json={"error_type": "concept"},
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    success_log = UserAnswerLog(
        user_id=user.id,
        atom_id=lesson_atom.id,
        is_correct=True,
        user_answer_json={},
        created_at=datetime.utcnow() - timedelta(hours=6),
    )
    db_session.add_all([error_log, success_log])
    db_session.commit()

    service = SRSService(db_session, user)

    schedule = service.register_answer(lesson_atom, False)
    db_session.commit()
    assert schedule.total_errors == 1
    assert schedule.last_outcome == "error"
    assert schedule.next_review_at is not None

    schedule = service.register_answer(lesson_atom, True)
    db_session.commit()
    assert schedule.review_count == 2
    assert schedule.streak == 1
    assert schedule.last_outcome == "success"

    service.register_reset(molecule)
    db_session.commit()
    stored = (
        db_session.query(UserMoleculeReview)
        .filter_by(user_id=user.id, molecule_id=molecule.id)
        .first()
    )
    assert stored is not None
    assert stored.total_resets >= 1
    assert stored.last_outcome == "reset"

    overview = service.build_overview()
    assert "settings" in overview
    assert overview["settings"]["allow_customization"] is True
    assert overview["retention_7_days"] is not None
    assert "advanced_stats" in overview

    error_overview = service.build_error_overview(include_examples=True)
    assert error_overview["total_errors"] >= 1
    assert error_overview["premium_suggestions"], "Premium users should receive targeted suggestions"
    entry = error_overview["molecules"][0]
    assert entry["molecule_id"] == molecule.id
    assert any(item["error_type"] == "concept" for item in entry["error_types"])
    assert entry["resets"] >= 1

    digest = service.coach_digest(capsule_id=capsule.id)
    assert "reviews" in digest and "errors" in digest
