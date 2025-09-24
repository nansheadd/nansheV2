"""Tests for the chat room helper utilities."""

from __future__ import annotations

from app.conversations.rooms import build_rooms_for_user
from app.conversations.schemas import ChannelDescriptor, ConversationScope
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.utility_models import UserCapsuleEnrollment
from tests.utils import create_user


def test_build_rooms_for_user_includes_general_room(db_session) -> None:
    user = create_user(db_session)

    rooms = build_rooms_for_user(db_session, user)

    assert rooms, "expected at least the general room"
    general = rooms[0]
    expected = ChannelDescriptor.from_params()
    assert general.key == expected.key
    assert general.scope == ConversationScope.GENERAL
    assert general.title
    assert general.description


def test_build_rooms_for_user_returns_enrolled_domains(db_session) -> None:
    user = create_user(db_session)

    capsule_python = Capsule(
        title="Capsule Python",
        domain="programming",
        area="python",
        main_skill="python",
        creator_id=user.id,
        is_public=True,
    )
    capsule_js = Capsule(
        title="Capsule JS",
        domain="programming",
        area="javascript",
        main_skill="javascript",
        creator_id=user.id,
        is_public=True,
    )

    db_session.add_all([capsule_python, capsule_js])
    db_session.commit()

    db_session.add_all(
        [
            UserCapsuleEnrollment(user_id=user.id, capsule_id=capsule_python.id),
            UserCapsuleEnrollment(user_id=user.id, capsule_id=capsule_js.id),
        ]
    )
    db_session.commit()

    rooms = build_rooms_for_user(db_session, user)

    domain_rooms = [room for room in rooms if room.scope == ConversationScope.DOMAIN]
    assert len(domain_rooms) == 2

    keys = {room.key for room in domain_rooms}
    assert "domain:programming:javascript" in keys
    assert "domain:programming:python" in keys
