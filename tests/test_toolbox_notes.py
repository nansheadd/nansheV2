from __future__ import annotations

import pytest

from app.crud import toolbox_notes_crud
from tests.utils import create_user, create_capsule_graph


@pytest.fixture()
def user(db_session):
    return create_user(db_session)


def test_create_general_note(db_session, user):
    note = toolbox_notes_crud.create_note(
        db_session,
        user,
        molecule_id=None,
        title="Note générale",
        content="Contenu libre",
    )

    assert note.id is not None
    assert note.molecule_id is None
    assert note.title == "Note générale"
    assert note.content == "Contenu libre"


def test_list_notes_filters_by_molecule(db_session, user):
    _, molecule, *_ = create_capsule_graph(db_session, user_id=user.id)

    general_note = toolbox_notes_crud.create_note(
        db_session,
        user,
        molecule_id=None,
        title="Note générale",
        content="Notes pour tout",
    )
    molecule_note = toolbox_notes_crud.create_note(
        db_session,
        user,
        molecule_id=molecule.id,
        title="Note ciblée",
        content="Notes pour la molécule",
    )

    all_notes = toolbox_notes_crud.list_notes(db_session, user)
    assert {note.id for note in all_notes} == {general_note.id, molecule_note.id}

    molecule_notes = toolbox_notes_crud.list_notes(db_session, user, molecule_id=molecule.id)
    assert [note.id for note in molecule_notes] == [molecule_note.id]


def test_create_note_invalid_molecule(db_session, user):
    with pytest.raises(ValueError):
        toolbox_notes_crud.create_note(
            db_session,
            user,
            molecule_id=999,
            title="Note",
            content="",
        )
