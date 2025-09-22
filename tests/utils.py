"""Utility helpers for test factories."""

from __future__ import annotations

from datetime import datetime

from app.models.capsule.atom_model import Atom, AtomContentType
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.granule_model import Granule
from app.models.capsule.language_roadmap_model import Skill, SkillType, Unit
from app.models.capsule.molecule_model import Molecule
from app.models.user.user_model import User
from app.models.vote.feature_vote_model import FeaturePoll, FeaturePollOption


def create_user(db, **kwargs) -> User:
    defaults = {
        "username": "user",
        "email": "user@example.com",
        "hashed_password": "x",
        "is_active": True,
        "is_superuser": False,
        "is_email_verified": True,
        "created_at": datetime.utcnow(),
    }
    defaults.update(kwargs)
    user = User(**defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_feature_poll(
    db,
    *,
    slug: str = "test-poll",
    title: str = "Sondage",
    option_titles: list[str] | None = None,
    **kwargs,
) -> FeaturePoll:
    defaults = {
        "slug": slug,
        "title": title,
        "description": kwargs.pop("description", None),
        "is_active": kwargs.pop("is_active", True),
        "starts_at": kwargs.pop("starts_at", None),
        "ends_at": kwargs.pop("ends_at", None),
        "max_votes_free": kwargs.pop("max_votes_free", 1),
        "max_votes_premium": kwargs.pop("max_votes_premium", 3),
    }
    defaults.update(kwargs)
    poll = FeaturePoll(**defaults)

    titles = option_titles or ["Option A", "Option B", "Option C"]
    for index, option_title in enumerate(titles):
        poll.options.append(
            FeaturePollOption(title=option_title, position=index)
        )

    db.add(poll)
    db.commit()
    db.refresh(poll)
    for option in poll.options:
        db.refresh(option)
    return poll


def ensure_skill(db, code: str = "generic") -> Skill:
    skill = db.query(Skill).filter_by(code=code).first()
    if skill:
        return skill
    skill = Skill(code=code, name=code.title(), type=SkillType.core, unit=Unit.items)
    db.add(skill)
    db.commit()
    return skill


def create_capsule_graph(db, user_id: int):
    ensure_skill(db)
    capsule = Capsule(
        title="Test Capsule",
        domain="programming",
        area="python",
        main_skill="python",
        creator_id=user_id,
        is_public=True,
    )
    granule = Granule(order=1, title="Chapitre 1")
    molecule = Molecule(order=1, title="Leçon 1")
    lesson_atom = Atom(order=1, title="Cours", content_type=AtomContentType.LESSON, content={})
    quiz_atom = Atom(order=2, title="Quiz", content_type=AtomContentType.QUIZ, content={})

    molecule.atoms.extend([lesson_atom, quiz_atom])
    granule.molecules.append(molecule)
    capsule.granules.append(granule)

    db.add(capsule)
    db.commit()
    db.refresh(capsule)
    return capsule, molecule, lesson_atom, quiz_atom
