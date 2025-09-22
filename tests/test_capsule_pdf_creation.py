import pytest
from fastapi import HTTPException

from app.models.user.user_model import SubscriptionStatus
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.atom_model import AtomContentType
from app.models.analytics.classification_feedback_model import ClassificationFeedback  # noqa: F401 - ensure mapper registration
from app.services.services.capsule_service import CapsuleService
from app.services.services.capsules.base_builder import BaseCapsuleBuilder
from tests.utils import create_user


def test_create_capsule_from_document_requires_premium(db_session):
    user = create_user(db_session, subscription_status=SubscriptionStatus.FREE)
    service = CapsuleService(db=db_session, user=user)

    with pytest.raises(HTTPException) as exc_info:
        service.create_capsule_from_document(
            source_text="contenu",
            title="Capsule",
            domain="others",
            area="generic",
            main_skill="capsule",
        )

    assert exc_info.value.status_code == 403


def test_create_capsule_from_document_populates_structure(db_session, monkeypatch):
    premium_user = create_user(db_session, subscription_status=SubscriptionStatus.PREMIUM)
    service = CapsuleService(db=db_session, user=premium_user)

    # neutralise les badges/notifications pour le test unitaire
    monkeypatch.setattr("app.services.services.capsule_service.badge_crud.award_badge", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.services.capsule_service.badge_crud.award_pioneer_for_domain", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.services.capsule_service.badge_crud.award_pioneer_for_area", lambda *args, **kwargs: None)
    monkeypatch.setattr(CapsuleService, "_notify", lambda *args, **kwargs: None)

    class StubBuilder(BaseCapsuleBuilder):
        def __init__(self, db, capsule, user, *, source_material=None):
            super().__init__(db=db, capsule=capsule, user=user, source_material=source_material)

        def _generate_plan_from_source(self, db, capsule, source_material):
            return {
                "overview": {
                    "title": capsule.title,
                    "domain": capsule.domain,
                    "area": capsule.area,
                    "main_skill": capsule.main_skill,
                },
                "levels": [
                    {
                        "level_title": "Niveau 1",
                        "xp_target": 120,
                        "summary": "Introduction au document",
                        "chapters": [
                            {
                                "chapter_title": "Chapitre 1",
                                "chapter_summary": "Résumé du document",
                                "learning_objectives": ["Objectif 1"],
                                "key_points": ["Point clé"],
                                "source_excerpt": ["Passage extrait"],
                                "assessment_hint": "Créer un quiz simple",
                            }
                        ],
                    }
                ],
            }

        def _get_molecule_recipe(self, molecule):
            return [{"type": AtomContentType.LESSON}]

        def _build_atom_content(self, atom_type, molecule, context_atoms, difficulty=None):
            return {"text": "Contenu généré"}

    monkeypatch.setattr(
        "app.services.services.capsule_service._get_builder_for_capsule",
        lambda db, capsule, user, source_material=None: StubBuilder(
            db=db,
            capsule=capsule,
            user=user,
            source_material=source_material,
        ),
    )

    capsule = service.create_capsule_from_document(
        source_text="Texte issu du PDF",
        title="Capsule premium",
        domain="others",
        area="custom",
        main_skill="doc_skill",
    )

    stored_capsule = db_session.get(Capsule, capsule.id)
    assert stored_capsule is not None
    assert stored_capsule.learning_plan_json is not None
    first_level = stored_capsule.learning_plan_json["levels"][0]
    first_chapter = first_level["chapters"][0]
    assert first_chapter["chapter_summary"] == "Résumé du document"

    granules = stored_capsule.granules
    assert len(granules) == 1
    molecules = granules[0].molecules
    assert len(molecules) == 1
    atoms = molecules[0].atoms
    assert atoms and atoms[0].content.get("text") == "Contenu généré"
