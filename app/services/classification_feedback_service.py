from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.taxonomy_skills import SKILL_HIERARCHY
from app.models.analytics.classification_feedback_model import ClassificationFeedback
from app.models.analytics.vector_store_model import VectorStore
from app.models.user.user_model import User
from app.services.rag_utils import get_embedding
from app.core.embeddings import ensure_dimension
from app.core import ai_service


class ClassificationFeedbackService:
    """Orchestre la collecte de feedback classification et l'enrichissement du RAG."""

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_taxonomy_options(self) -> Dict[str, List[Dict[str, Any]]]:
        base: Dict[str, set[str]] = {}
        for domain, data in SKILL_HIERARCHY.items():
            areas = data.get("areas", {})
            base[domain] = {area for area in areas.keys()}

        dynamic_rows = (
            self.db.query(VectorStore.domain, VectorStore.area)
            .filter(VectorStore.domain.isnot(None))
            .distinct()
            .all()
        )
        for domain, area in dynamic_rows:
            if not domain:
                continue
            area_value = area or "generic"
            base.setdefault(domain, set()).add(area_value)

        options = [
            {"domain": domain, "areas": sorted(filter(None, areas))}
            for domain, areas in sorted(base.items())
        ]
        return {"domains": options}

    def record_feedback(self, payload: "ClassificationFeedbackPayload") -> Dict[str, Any]:
        text = payload.input_text.strip()
        if not text:
            raise ValueError("Le texte d'entrée est vide.")

        taxonomy = self.get_taxonomy_options()["domains"]
        known_domains = {entry["domain"]: set(entry["areas"]) for entry in taxonomy}

        final_domain = (payload.final_domain or payload.predicted_domain or "others").strip()
        final_area = (payload.final_area or payload.predicted_area or "generic").strip()
        final_skill = (payload.final_skill or payload.predicted_skill or final_domain).strip()

        is_new_domain = final_domain not in known_domains
        if is_new_domain:
            known_domains[final_domain] = set()
        is_new_area = final_area not in known_domains[final_domain]
        if is_new_area:
            known_domains[final_domain].add(final_area)

        enrichment_meta: Dict[str, Any] = {}
        if is_new_domain or is_new_area:
            try:
                ai_metadata = ai_service.generate_classification_metadata(
                    topic=text,
                    domain=final_domain,
                    area=final_area,
                    model_choice="gpt-5-mini-2025-08-07",
                )
                if ai_metadata:
                    enrichment_meta["ai_metadata"] = ai_metadata
            except Exception:
                pass

        feedback = ClassificationFeedback(
            user_id=self.user.id,
            input_text=text,
            predicted_domain=payload.predicted_domain,
            predicted_area=payload.predicted_area,
            predicted_skill=payload.predicted_skill,
            final_domain=final_domain,
            final_area=final_area,
            final_skill=final_skill,
            is_correct=payload.is_correct,
            notes=payload.notes,
            metadata_=payload.metadata or None,
        )
        if enrichment_meta:
            metadata = feedback.metadata_ or {}
            metadata.update(enrichment_meta)
            feedback.metadata_ = metadata

        self.db.add(feedback)
        self.db.flush([feedback])

        embedding = ensure_dimension(get_embedding(text))
        vector_entry = VectorStore(
            chunk_text=text,
            embedding=embedding,
            domain=final_domain,
            area=final_area,
            skill=final_skill,
            metadata_={
                "source": "user_feedback",
                "feedback_id": feedback.id,
                "user_id": self.user.id,
                "is_correct": payload.is_correct,
                "notes": payload.notes,
                **enrichment_meta,
            },
            source_language="fr",
            content_type="taxonomy_feedback",
        )
        self.db.add(vector_entry)
        self.db.commit()
        self.db.refresh(feedback)
        self.db.refresh(vector_entry)

        # Renvoie les options actualisées (incluant les nouvelles valeurs)
        updated_options = self.get_taxonomy_options()

        return {
            "feedback_id": feedback.id,
            "training_entry_id": vector_entry.id,
            "input_text": text,
            "domain": final_domain,
            "area": final_area,
            "main_skill": final_skill,
            "added_to_training": True,
            "taxonomy": updated_options,
            "created_at": feedback.created_at or datetime.utcnow(),
        }


class ClassificationFeedbackPayload:
    """Objet simple pour porter les données de feedback."""

    def __init__(
        self,
        *,
        input_text: str,
        predicted_domain: Optional[str],
        predicted_area: Optional[str],
        predicted_skill: Optional[str],
        is_correct: bool,
        final_domain: Optional[str],
        final_area: Optional[str],
        final_skill: Optional[str],
        notes: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ):
        self.input_text = input_text
        self.predicted_domain = predicted_domain
        self.predicted_area = predicted_area
        self.predicted_skill = predicted_skill
        self.is_correct = is_correct
        self.final_domain = final_domain
        self.final_area = final_area
        self.final_skill = final_skill
        self.notes = notes
        self.metadata = metadata

        if not self.is_correct and not (self.final_domain and self.final_area):
            raise ValueError("Une classification corrigée doit préciser un domaine et une aire.")
