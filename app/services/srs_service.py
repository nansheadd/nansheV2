"""Utilities for spaced repetition scheduling and error journals."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.capsule.atom_model import Atom
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.granule_model import Granule
from app.models.progress.user_answer_log_model import UserAnswerLog
from app.models.progress.user_atomic_progress import UserAtomProgress
from app.models.progress.user_molecule_review_model import UserMoleculeReview
from app.models.user.user_model import SubscriptionStatus, User


class SRSService:
    """High level helper combining SRS scheduling and error analytics."""

    DEFAULT_EASE_FACTOR = 2.5
    MIN_EASE_FACTOR = 1.3
    ERROR_REVIEW_DELAY_HOURS = 8

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.user_id = user.id
        self._is_premium = (
            getattr(user, "subscription_status", SubscriptionStatus.FREE)
            == SubscriptionStatus.PREMIUM
        )

    # ------------------------------------------------------------------
    # Core update operations
    # ------------------------------------------------------------------
    def register_answer(self, atom: Atom, is_correct: bool) -> UserMoleculeReview:
        """Update or create the SRS schedule when an answer is logged."""

        molecule = atom.molecule
        schedule = self._get_or_create_schedule(molecule.id)
        now = datetime.utcnow()

        schedule.review_count = (schedule.review_count or 0) + 1
        schedule.last_review_at = now

        if is_correct:
            schedule.streak = (schedule.streak or 0) + 1
            schedule.success_count = (schedule.success_count or 0) + 1
            schedule.ease_factor = min(
                (schedule.ease_factor or self.DEFAULT_EASE_FACTOR) + 0.1,
                3.0,
            )
            if schedule.review_count == 1:
                schedule.interval_days = 1.0
            elif schedule.review_count == 2:
                schedule.interval_days = 3.0
            else:
                base_interval = schedule.interval_days or 1.0
                schedule.interval_days = max(1.0, base_interval * schedule.ease_factor)
            schedule.last_outcome = "success"
        else:
            schedule.streak = 0
            schedule.total_errors = (schedule.total_errors or 0) + 1
            schedule.ease_factor = max(
                self.MIN_EASE_FACTOR,
                (schedule.ease_factor or self.DEFAULT_EASE_FACTOR) - 0.2,
            )
            schedule.interval_days = max(
                0.25, self.ERROR_REVIEW_DELAY_HOURS / 24.0
            )
            schedule.last_outcome = "error"
            schedule.last_error_at = now

        delay = schedule.interval_days or 1.0
        schedule.next_review_at = now + timedelta(days=delay)
        schedule.updated_at = now

        self.db.add(schedule)
        self.db.flush([schedule])
        return schedule

    def register_reset(self, molecule: Molecule) -> UserMoleculeReview:
        """Penalise schedule when the learner resets a molecule."""

        schedule = self._get_or_create_schedule(molecule.id)
        now = datetime.utcnow()

        schedule.total_resets = (schedule.total_resets or 0) + 1
        schedule.streak = 0
        schedule.interval_days = min(schedule.interval_days or 1.0, 1.0)
        soonest = now + timedelta(hours=self.ERROR_REVIEW_DELAY_HOURS)
        if schedule.next_review_at is None or schedule.next_review_at > soonest:
            schedule.next_review_at = soonest
        schedule.last_outcome = "reset"
        schedule.updated_at = now

        self.db.add(schedule)
        self.db.flush([schedule])
        return schedule

    # ------------------------------------------------------------------
    # Public reporting helpers
    # ------------------------------------------------------------------
    def build_overview(self, limit: int | None = None) -> dict:
        """Return SRS plan summary suitable for API responses."""

        schedules = (
            self.db.query(UserMoleculeReview)
            .options(
                selectinload(UserMoleculeReview.molecule)
                .selectinload(Molecule.granule)
                .selectinload(Granule.capsule)
            )
            .filter(UserMoleculeReview.user_id == self.user_id)
            .order_by(UserMoleculeReview.next_review_at.asc().nullsfirst())
            .all()
        )

        now = datetime.utcnow()
        due_count = 0
        overdue_count = 0
        entries: List[dict] = []

        for schedule in schedules:
            molecule = schedule.molecule
            capsule = getattr(getattr(molecule, "granule", None), "capsule", None)
            next_review = schedule.next_review_at
            due_in_hours = None
            if next_review:
                delta = next_review - now
                due_in_hours = round(delta.total_seconds() / 3600, 2)
                if next_review <= now:
                    due_count += 1
                    if (schedule.last_outcome or "") != "success":
                        overdue_count += 1

            entries.append(
                {
                    "molecule_id": molecule.id,
                    "molecule_title": molecule.title,
                    "capsule_id": getattr(capsule, "id", None),
                    "capsule_title": getattr(capsule, "title", None),
                    "next_review_at": next_review.isoformat() if next_review else None,
                    "due_in_hours": due_in_hours,
                    "interval_days": round(schedule.interval_days or 0, 2),
                    "streak": schedule.streak or 0,
                    "review_count": schedule.review_count or 0,
                    "total_errors": schedule.total_errors or 0,
                    "total_resets": schedule.total_resets or 0,
                    "last_outcome": schedule.last_outcome,
                }
            )

        if limit is not None:
            entries = entries[:limit]

        overview = {
            "due_count": due_count,
            "overdue_count": overdue_count,
            "next_reviews": entries,
            "retention_7_days": self._compute_retention_ratio(7),
            "retention_30_days": self._compute_retention_ratio(30),
            "settings": {
                "default_interval_days": 1.0,
                "default_ease_factor": self.DEFAULT_EASE_FACTOR,
                "allow_customization": self._is_premium,
            },
        }

        if self._is_premium:
            overview["advanced_stats"] = {
                "average_interval_days": self._calculate_average_interval(schedules),
                "success_rate": self._compute_success_rate(schedules),
            }

        return overview

    def build_error_overview(
        self,
        limit: int | None = None,
        include_examples: bool = False,
    ) -> dict:
        """Aggregate recent mistakes per molecule and error type."""

        error_logs = (
            self.db.query(UserAnswerLog)
            .options(
                selectinload(UserAnswerLog.atom)
                .selectinload(Atom.molecule)
                .selectinload(Molecule.granule)
                .selectinload(Granule.capsule)
            )
            .filter(
                UserAnswerLog.user_id == self.user_id,
                UserAnswerLog.is_correct.is_(False),
            )
            .order_by(UserAnswerLog.created_at.desc())
            .all()
        )

        reset_map = self._build_reset_map()
        aggregated: Dict[int, dict] = {}

        for log in error_logs:
            atom = log.atom
            molecule = atom.molecule
            if molecule is None:
                continue

            bucket = aggregated.setdefault(
                molecule.id,
                {
                    "molecule_id": molecule.id,
                    "molecule_title": molecule.title,
                    "capsule_id": getattr(
                        getattr(getattr(molecule, "granule", None), "capsule", None),
                        "id",
                        None,
                    ),
                    "total_errors": 0,
                    "error_types": {},
                    "examples": [],
                    "last_error_at": None,
                    "resets": reset_map.get(molecule.id, 0),
                },
            )

            bucket["total_errors"] += 1
            bucket["last_error_at"] = max(
                bucket["last_error_at"], log.created_at
            ) if bucket["last_error_at"] else log.created_at

            error_type = self._resolve_error_type(log.user_answer_json)
            bucket["error_types"][error_type] = bucket["error_types"].get(error_type, 0) + 1

            if include_examples and len(bucket["examples"]) < 3:
                bucket["examples"].append(
                    {
                        "atom_id": atom.id,
                        "atom_title": atom.title,
                        "submitted_answer": self._compact_json(log.user_answer_json),
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                    }
                )

        entries = sorted(
            aggregated.values(), key=lambda item: item["total_errors"], reverse=True
        )
        if limit is not None:
            entries = entries[:limit]

        for entry in entries:
            entry["error_types"] = [
                {"error_type": key, "count": value}
                for key, value in sorted(
                    entry["error_types"].items(), key=lambda item: item[1], reverse=True
                )
            ]
            if entry["last_error_at"]:
                entry["last_error_at"] = entry["last_error_at"].isoformat()
            entry["suggested_action"] = self._build_suggestion(entry)

        overview = {
            "total_errors": sum(entry["total_errors"] for entry in entries),
            "molecules": entries,
        }

        if self._is_premium and entries:
            overview["premium_suggestions"] = [
                self._build_premium_suggestion(entry) for entry in entries
            ]
        else:
            overview["premium_suggestions"] = []

        return overview

    # ------------------------------------------------------------------
    # Coach helper
    # ------------------------------------------------------------------
    def coach_digest(self, capsule_id: int | None = None) -> dict:
        """Return concise strings summarising schedule and errors for coach prompts."""

        plan = self.build_overview()
        errors = self.build_error_overview(limit=5)

        next_reviews = [
            entry
            for entry in plan["next_reviews"]
            if capsule_id is None or entry["capsule_id"] == capsule_id
        ][:3]

        molecules_with_errors = [
            entry
            for entry in errors["molecules"]
            if capsule_id is None or entry["capsule_id"] == capsule_id
        ][:3]

        def _format_review(entry: dict) -> str:
            due = entry.get("due_in_hours")
            if due is None:
                return f"{entry['molecule_title']} (planifié)"
            if due <= 0:
                return f"{entry['molecule_title']} — en retard"
            return f"{entry['molecule_title']} — dans {due:.1f}h"

        def _format_error(entry: dict) -> str:
            if not entry.get("error_types"):
                return f"{entry['molecule_title']} ({entry['total_errors']} erreurs)"
            top_type = entry["error_types"][0]["error_type"]
            return f"{entry['molecule_title']} ({entry['total_errors']} erreurs, axe {top_type})"

        reviews_text = "\n".join(_format_review(entry) for entry in next_reviews)
        errors_text = "\n".join(_format_error(entry) for entry in molecules_with_errors)

        return {
            "reviews": reviews_text or "Aucune révision urgente.",
            "errors": errors_text or "Aucune erreur récente détectée.",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_or_create_schedule(self, molecule_id: int) -> UserMoleculeReview:
        schedule = (
            self.db.query(UserMoleculeReview)
            .filter_by(user_id=self.user_id, molecule_id=molecule_id)
            .first()
        )
        if schedule:
            return schedule

        schedule = UserMoleculeReview(
            user_id=self.user_id,
            molecule_id=molecule_id,
            interval_days=1.0,
            ease_factor=self.DEFAULT_EASE_FACTOR,
            next_review_at=datetime.utcnow(),
            total_resets=self._count_resets_for_molecule(molecule_id),
        )
        self.db.add(schedule)
        self.db.flush([schedule])
        return schedule

    def _count_resets_for_molecule(self, molecule_id: int) -> int:
        total = (
            self.db.query(func.coalesce(func.sum(UserAtomProgress.reset_count), 0))
            .join(Atom, Atom.id == UserAtomProgress.atom_id)
            .filter(
                UserAtomProgress.user_id == self.user_id,
                Atom.molecule_id == molecule_id,
            )
            .scalar()
        )
        return int(total or 0)

    def _build_reset_map(self) -> Dict[int, int]:
        rows = (
            self.db.query(UserAtomProgress, Atom)
            .join(Atom, Atom.id == UserAtomProgress.atom_id)
            .filter(UserAtomProgress.user_id == self.user_id)
            .all()
        )
        reset_map: Dict[int, int] = {}
        for progress, atom in rows:
            reset_map[atom.molecule_id] = reset_map.get(atom.molecule_id, 0) + (
                progress.reset_count or 0
            )
        return reset_map

    def _resolve_error_type(self, payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ("error_type", "type", "category", "reason"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().lower()
        return "autre"

    def _compact_json(self, payload: Any) -> str:
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:  # pragma: no cover - defensive fallback
            return str(payload)

    def _build_suggestion(self, entry: dict) -> str:
        if entry["total_errors"] == 0:
            return "Révision rapide recommandée."
        top_error = entry.get("error_types")
        if top_error:
            label = top_error[0]["error_type"]
            return f"Revoir la notion ciblée ({label}) avec un exercice guidé."
        return "Refaire des exercices similaires pour ancrer la notion."

    def _build_premium_suggestion(self, entry: dict) -> str:
        if not entry.get("error_types"):
            return f"Planifier une session de consolidation sur {entry['molecule_title']}."
        top = entry["error_types"][0]
        return (
            f"Configurer une série d'exercices '{top['error_type']}' pour {entry['molecule_title']} "
            "et suivre la progression dans le carnet premium."
        )

    def _compute_retention_ratio(self, days: int) -> float | None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        logs = (
            self.db.query(UserAnswerLog)
            .join(Atom, Atom.id == UserAnswerLog.atom_id)
            .filter(
                UserAnswerLog.user_id == self.user_id,
                UserAnswerLog.created_at >= cutoff,
            )
            .all()
        )
        if not logs:
            return None
        successes = sum(1 for log in logs if log.is_correct)
        return round(successes / len(logs), 3)

    def _calculate_average_interval(self, schedules: Iterable[UserMoleculeReview]) -> float | None:
        intervals = [schedule.interval_days for schedule in schedules if schedule.interval_days]
        if not intervals:
            return None
        return round(sum(intervals) / len(intervals), 2)

    def _compute_success_rate(self, schedules: Iterable[UserMoleculeReview]) -> float | None:
        total_reviews = 0
        total_success = 0
        for schedule in schedules:
            total_reviews += schedule.review_count or 0
            total_success += schedule.success_count or 0
        if total_reviews == 0:
            return None
        return round(total_success / total_reviews, 3)


__all__ = ["SRSService"]
