import pytest
from fastapi import HTTPException

from app.models.capsule.atom_model import Atom, AtomContentType
from app.models.capsule.language_roadmap_model import Skill
from app.models.capsule.utility_models import UserCapsuleProgress, UserCapsuleEnrollment
from app.models.user.user_model import SubscriptionStatus
from app.services.progress_service import calculate_capsule_xp_distribution, ProgressService
from app.services.services.capsule_service import CapsuleService
from tests.utils import create_user, create_capsule_graph


class DummyBuilder:
    def __init__(self, db, capsule, user):
        self.db = db
        self.capsule = capsule
        self.user = user

    def create_bonus_atom(self, molecule, content_type, title, difficulty=None):
        new_atom = Atom(
            title=title,
            order=len(molecule.atoms) + 1,
            content_type=content_type,
            content={"text": "bonus"},
            difficulty=difficulty,
            molecule_id=molecule.id,
            is_bonus=True,
        )
        self.db.add(new_atom)
        self.db.flush([new_atom])
        return new_atom


def test_bonus_xp_distribution_capped(db_session):
    user = create_user(db_session, subscription_status=SubscriptionStatus.PREMIUM)
    capsule, molecule, *_ = create_capsule_graph(db_session, user.id)

    bonus_atoms = [
        Atom(order=3 + idx, title=f"Bonus {idx}", content_type=AtomContentType.QUIZ, content={}, molecule_id=molecule.id, is_bonus=True)
        for idx in range(3)
    ]
    db_session.add_all(bonus_atoms)
    db_session.commit()

    atom_xp_map, _ = calculate_capsule_xp_distribution(capsule)
    bonus_total = sum(atom_xp_map[atom.id] for atom in bonus_atoms)
    assert bonus_total <= 50


def test_progress_service_records_bonus_xp(db_session):
    user = create_user(db_session, subscription_status=SubscriptionStatus.PREMIUM)
    capsule, molecule, lesson_atom, quiz_atom = create_capsule_graph(db_session, user.id)
    bonus_atom = Atom(
        order=3,
        title="Bonus",
        content_type=AtomContentType.QUIZ,
        content={"text": "bonus"},
        molecule_id=molecule.id,
        is_bonus=True,
    )
    db_session.add(bonus_atom)
    db_session.commit()

    atom_xp_map, _ = calculate_capsule_xp_distribution(capsule)
    expected_xp = atom_xp_map[bonus_atom.id]

    skill_id = db_session.query(Skill).first().id
    progress = UserCapsuleProgress(user_id=user.id, capsule_id=capsule.id, skill_id=skill_id, xp=0, bonus_xp=0)
    db_session.add(progress)
    db_session.commit()

    service = ProgressService(db_session, user.id)
    service.record_atom_completion(bonus_atom.id)

    db_session.refresh(progress)
    assert progress.xp == 0
    assert progress.bonus_xp == pytest.approx(expected_xp)


def test_generate_bonus_requires_premium(db_session, monkeypatch):
    user = create_user(db_session, subscription_status=SubscriptionStatus.FREE)
    capsule, molecule, *_ = create_capsule_graph(db_session, user.id)
    service = CapsuleService(db=db_session, user=user)

    with pytest.raises(HTTPException) as exc:
        service.generate_bonus_atom(molecule.id, kind='exercise')
    assert exc.value.status_code == 403


def test_generate_bonus_creates_atom(db_session, monkeypatch):
    creator = create_user(db_session, subscription_status=SubscriptionStatus.PREMIUM)
    other = create_user(db_session, username='other', email='other@example.com', subscription_status=SubscriptionStatus.FREE)
    capsule, molecule, *_ = create_capsule_graph(db_session, creator.id)

    skill_id = db_session.query(Skill).first().id

    db_session.add_all([
        UserCapsuleEnrollment(user_id=creator.id, capsule_id=capsule.id),
        UserCapsuleEnrollment(user_id=other.id, capsule_id=capsule.id),
        UserCapsuleProgress(user_id=creator.id, capsule_id=capsule.id, skill_id=skill_id, xp=0, bonus_xp=0),
    ])
    db_session.commit()

    def stub_builder(db, capsule_arg, user_arg):  # noqa: ANN001
        return DummyBuilder(db, capsule_arg, user_arg)

    monkeypatch.setattr('app.services.services.capsule_service._get_builder_for_capsule', stub_builder)

    service = CapsuleService(db=db_session, user=creator)
    atoms = service.generate_bonus_atom(molecule.id, kind='exercise')

    bonus_atoms = [atom for atom in atoms if getattr(atom, 'is_bonus', False)]
    assert bonus_atoms, "Expected at least one bonus atom in response"
    last_bonus = bonus_atoms[-1]
    assert last_bonus.xp_value <= 50
    assert last_bonus.content_type == AtomContentType.QUIZ
