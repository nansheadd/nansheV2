from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session, joinedload

from app.models.capsule.molecule_model import Molecule
from app.models.capsule.granule_model import Granule
from app.models.toolbox.molecule_note_model import MoleculeNote
from app.models.user.user_model import User


def list_notes(db: Session, user: User, molecule_id: int | None = None) -> list[MoleculeNote]:
    query = (
        db.query(MoleculeNote)
        .options(
            joinedload(MoleculeNote.molecule)
            .joinedload(Molecule.granule)
            .joinedload(Granule.capsule)
        )
        .filter(MoleculeNote.user_id == user.id)
        .order_by(MoleculeNote.updated_at.desc())
    )
    if molecule_id:
        query = query.filter(MoleculeNote.molecule_id == molecule_id)
    return query.all()


def create_note(
    db: Session,
    user: User,
    *,
    molecule_id: int,
    title: str,
    content: str,
) -> MoleculeNote:
    molecule = db.get(Molecule, molecule_id)
    if not molecule:
        raise ValueError("Molecule not found")

    note = MoleculeNote(
        user_id=user.id,
        molecule_id=molecule.id,
        title=title.strip() or "Sans titre",
        content=content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def get_note_for_user(db: Session, user: User, note_id: int) -> MoleculeNote | None:
    return (
        db.query(MoleculeNote)
        .options(
            joinedload(MoleculeNote.molecule)
            .joinedload(Molecule.granule)
            .joinedload(Granule.capsule)
        )
        .filter(MoleculeNote.id == note_id, MoleculeNote.user_id == user.id)
        .first()
    )


def update_note(
    db: Session,
    note: MoleculeNote,
    *,
    title: str | None = None,
    content: str | None = None,
) -> MoleculeNote:
    if title is not None:
        note.title = title.strip() or "Sans titre"
    if content is not None:
        note.content = content

    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note: MoleculeNote) -> None:
    db.delete(note)
    db.commit()


def bulk_delete_notes(db: Session, notes: Iterable[MoleculeNote]) -> int:
    count = 0
    for note in notes:
        db.delete(note)
        count += 1
    if count:
        db.commit()
    return count
