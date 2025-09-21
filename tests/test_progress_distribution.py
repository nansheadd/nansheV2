from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.progress_service import (
    TOTAL_XP,
    calculate_capsule_xp_distribution,
)


def build_atom(atom_id: int, content_type: str, order: int = 1):
    return SimpleNamespace(id=atom_id, content_type=content_type, order=order)


def build_molecule(molecule_id: int, order: int, atoms):
    return SimpleNamespace(id=molecule_id, order=order, atoms=list(atoms))


def build_granule(granule_id: int, order: int, molecules):
    return SimpleNamespace(id=granule_id, order=order, molecules=list(molecules))


def build_capsule(granules):
    return SimpleNamespace(granules=list(granules))


def test_calculate_capsule_xp_distribution_totals():
    capsule = build_capsule(
        [
            build_granule(
                1,
                1,
                [
                    build_molecule(
                        10,
                        1,
                        [
                            build_atom(100, "lesson"),
                            build_atom(101, "quiz"),
                            build_atom(102, "code_challenge"),
                        ],
                    ),
                    build_molecule(
                        11,
                        2,
                        [
                            build_atom(110, "quiz"),
                            build_atom(111, "quiz"),
                        ],
                    ),
                ],
            ),
            build_granule(
                2,
                2,
                [
                    build_molecule(
                        20,
                        1,
                        [
                            build_atom(200, "lesson"),
                            build_atom(201, "code_project_brief"),
                        ],
                    ),
                ],
            ),
        ]
    )

    atom_map, molecule_totals = calculate_capsule_xp_distribution(capsule)

    assert sum(atom_map.values()) == TOTAL_XP
    assert sum(molecule_totals.values()) == TOTAL_XP
    assert set(molecule_totals) == {10, 11, 20}


@pytest.mark.parametrize(
    "primary_type, secondary_type",
    [
        ("code_challenge", "quiz"),
        ("lesson", "quiz"),
        ("code_project_brief", "quiz"),
    ],
)
def test_weighted_atoms_receive_more_xp(primary_type: str, secondary_type: str):
    capsule = build_capsule(
        [
            build_granule(
                1,
                1,
                [
                    build_molecule(
                        99,
                        1,
                        [
                            build_atom(900, primary_type),
                            build_atom(901, secondary_type),
                        ],
                    ),
                ],
            )
        ]
    )

    atom_map, molecule_totals = calculate_capsule_xp_distribution(capsule)

    assert molecule_totals[99] == TOTAL_XP
    xp_primary = atom_map[900]
    xp_secondary = atom_map[901]
    assert xp_primary > xp_secondary
    assert xp_primary + xp_secondary == TOTAL_XP


def test_empty_capsule_returns_zero_maps():
    capsule = build_capsule([])
    atom_map, molecule_totals = calculate_capsule_xp_distribution(capsule)
    assert atom_map == {}
    assert molecule_totals == {}
