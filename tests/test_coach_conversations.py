from __future__ import annotations

from app.core import ai_service
from app.crud import coach_conversation_crud, toolbox_crud
from app.models.toolbox.coach_conversation_model import CoachConversationLocation
from tests.utils import create_capsule_graph, create_user


def _stub_ai_response(monkeypatch, response_text: str = "Réponse du coach") -> None:
    payload = {
        "response": response_text,
        "suggestions": ["Suggestion"],
        "next_steps": ["Étape suivante"],
    }

    def _fake_call_ai_and_log(**_: dict):
        return payload

    monkeypatch.setattr(ai_service, "call_ai_and_log", _fake_call_ai_and_log)


def test_ask_coach_persists_messages_with_location(db_session, monkeypatch) -> None:
    user = create_user(db_session, username="coach_user")
    capsule, molecule, *_ = create_capsule_graph(db_session, user.id)

    _stub_ai_response(monkeypatch, response_text="Analyse détaillée")

    result = toolbox_crud.ask_coach(
        db=db_session,
        user=user,
        message="Bonjour coach !",
        context={"capsuleId": capsule.id, "moleculeId": molecule.id},
        history=[],
        quick_action=None,
        selection=None,
    )

    assert result["response"] == "Analyse détaillée"
    assert result["thread_id"]

    threads = coach_conversation_crud.list_threads_for_user(db_session, user)
    assert len(threads) == 1

    thread = threads[0]
    assert thread.location == CoachConversationLocation.MOLECULE
    assert thread.capsule_id == capsule.id
    assert thread.molecule_id == molecule.id

    messages = coach_conversation_crud.list_messages_for_thread(db_session, thread)
    assert len(messages) == 2
    assert messages[0].role.value == "user"
    assert messages[0].content == "Bonjour coach !"
    assert messages[1].role.value == "coach"
    assert messages[1].content == "Analyse détaillée"
    assert messages[1].payload["raw_response"]["suggestions"] == ["Suggestion"]

    stats = coach_conversation_crud.fetch_thread_statistics(db_session, [thread.id])
    count, last_message_at = stats[thread.id]
    assert count == 2
    assert last_message_at == messages[-1].created_at


def test_conversations_are_partitioned_by_location(db_session, monkeypatch) -> None:
    user = create_user(db_session, username="multi_context")
    capsule, molecule, *_ = create_capsule_graph(db_session, user.id)

    _stub_ai_response(monkeypatch, response_text="Réponse générique")

    # Dashboard conversation
    toolbox_crud.ask_coach(
        db=db_session,
        user=user,
        message="Salut du dashboard",
        context={"path": "/dashboard"},
        history=[],
        quick_action=None,
        selection=None,
    )

    # Capsule level conversation
    toolbox_crud.ask_coach(
        db=db_session,
        user=user,
        message="Question capsule",
        context={"capsuleId": capsule.id},
        history=[],
        quick_action=None,
        selection=None,
    )

    # Molecule conversation (two messages to ensure reuse)
    toolbox_crud.ask_coach(
        db=db_session,
        user=user,
        message="Question molécule",
        context={"capsuleId": capsule.id, "moleculeId": molecule.id},
        history=[],
        quick_action=None,
        selection=None,
    )
    toolbox_crud.ask_coach(
        db=db_session,
        user=user,
        message="Relance molécule",
        context={"moleculeId": molecule.id},
        history=[],
        quick_action=None,
        selection=None,
    )

    threads = coach_conversation_crud.list_threads_for_user(db_session, user)
    assert len(threads) == 3

    by_signature = {
        (thread.location, thread.capsule_id, thread.molecule_id): thread for thread in threads
    }

    assert (CoachConversationLocation.DASHBOARD, None, None) in by_signature
    assert (CoachConversationLocation.CAPSULE, capsule.id, None) in by_signature
    assert (CoachConversationLocation.MOLECULE, capsule.id, molecule.id) in by_signature

    molecule_thread = by_signature[(CoachConversationLocation.MOLECULE, capsule.id, molecule.id)]
    molecule_messages = coach_conversation_crud.list_messages_for_thread(db_session, molecule_thread)
    assert len(molecule_messages) == 4
    assert [msg.role.value for msg in molecule_messages] == ["user", "coach", "user", "coach"]

    stats = coach_conversation_crud.fetch_thread_statistics(db_session, [thread.id for thread in threads])
    molecule_stats = stats[molecule_thread.id]
    assert molecule_stats[0] == 4
    assert molecule_stats[1] == molecule_messages[-1].created_at
