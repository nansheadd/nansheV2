import logging
import re
from sqlalchemy.orm import Session
from sqlalchemy import String, cast
from datetime import datetime, timedelta, timezone, date
from app.models.capsule.utility_models import UserCapsuleProgress
from app.models.progress.user_activity_log_model import UserActivityLog
from app.models.user.user_model import User  # <-- Import the User model
from app.models.progress.user_atomic_progress import UserAtomProgress

from app.models.capsule.atom_model import Atom
from app.models.capsule.capsule_model import Capsule
from app.models.capsule.molecule_model import Molecule
from app.models.capsule.granule_model import Granule
from app.crud import badge_crud

logger = logging.getLogger(__name__)

TOTAL_XP = 60000
BONUS_XP_PER_MOLECULE = 50

ATOM_XP_WEIGHTS = {
    "lesson": 4,
    "quiz": 2,
    "code_example": 2,
    "code_challenge": 5,
    "live_code_executor": 3,
    "code_sandbox_setup": 1,
    "code_project_brief": 4,
    "code_refactor": 3,
    "exercise": 3,
    "vocabulary": 2,
    "grammar": 2,
    "dialogue": 3,
    "fill_in_the_blank": 2,
    "translation": 2,
    "flashcards": 1,
    "essay_prompt": 3,
    "character": 2,
}
DEFAULT_ATOM_WEIGHT = 2


def _resolve_atom_weight(atom: Atom) -> int:
    raw = getattr(atom, "content_type", None)
    key = raw.value if hasattr(raw, "value") else raw
    return ATOM_XP_WEIGHTS.get(key, DEFAULT_ATOM_WEIGHT)


def calculate_capsule_xp_distribution(capsule: Capsule) -> tuple[dict[int, int], dict[int, int]]:
    """Retourne deux dictionnaires: XP par atome et XP total par molécule."""
    if not capsule.granules:
        return {}, {}

    molecules_ordered: list[Molecule] = []
    for granule in sorted(capsule.granules, key=lambda g: (g.order or 0, g.id)):
        molecules_ordered.extend(sorted(granule.molecules, key=lambda m: (m.order or 0, m.id)))

    molecule_count = len(molecules_ordered) or 1
    base_share = TOTAL_XP // molecule_count
    remainder = TOTAL_XP % molecule_count

    atom_xp: dict[int, int] = {}
    molecule_totals: dict[int, int] = {}

    for idx, molecule in enumerate(molecules_ordered):
        atoms = sorted(molecule.atoms, key=lambda a: (a.order or 0, a.id))
        if not atoms:
            molecule_totals[molecule.id] = base_share + (1 if idx < remainder else 0)
            continue

        core_atoms = [atom for atom in atoms if not getattr(atom, "is_bonus", False)]
        bonus_atoms = [atom for atom in atoms if getattr(atom, "is_bonus", False)]

        molecule_total = 0
        if core_atoms:
            molecule_total = base_share + (1 if idx < remainder else 0)

            weights = [_resolve_atom_weight(atom) for atom in core_atoms]
            total_weight = sum(weights) or len(core_atoms)
            allocated = 0
            for atom, weight in zip(core_atoms, weights):
                xp_value = int(molecule_total * weight / total_weight)
                atom_xp[atom.id] = xp_value
                allocated += xp_value

            remaining_core = molecule_total - allocated
            if remaining_core > 0:
                for atom in core_atoms:
                    atom_xp[atom.id] = atom_xp.get(atom.id, 0) + 1
                    remaining_core -= 1
                    if remaining_core == 0:
                        break

        if bonus_atoms:
            bonus_total = BONUS_XP_PER_MOLECULE
            if len(bonus_atoms) >= bonus_total:
                for index, atom in enumerate(bonus_atoms):
                    atom_xp[atom.id] = 1 if index < bonus_total else 0
            else:
                base_bonus = bonus_total // len(bonus_atoms)
                remainder_bonus = bonus_total % len(bonus_atoms)
                for index, atom in enumerate(bonus_atoms):
                    xp_value = base_bonus + (1 if index < remainder_bonus else 0)
                    atom_xp[atom.id] = xp_value

        molecule_totals[molecule.id] = molecule_total or (base_share + (1 if idx < remainder else 0))

    return atom_xp, molecule_totals

class ProgressService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        # Fetch the user and assign it to self.user
        self.user = self.db.query(User).get(self.user_id)
        self._activity_cache: dict | None = None

    def _invalidate_activity_cache(self) -> None:
        """Force le recalcul des agrégats de temps lors du prochain accès."""
        self._activity_cache = None

    # -----------------------------
    # Helpers: activity hygiene
    # -----------------------------

    def _close_stale_activity_logs(self, max_age_minutes: int = 120):
        """Clôture automatiquement les sessions sans `end_time` trop anciennes."""
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        stale_logs = (
            self.db.query(UserActivityLog)
            .filter(
                UserActivityLog.user_id == self.user_id,
                UserActivityLog.end_time.is_(None),
                UserActivityLog.start_time <= cutoff,
            )
            .all()
        )
        if not stale_logs:
            return
        for log in stale_logs:
            log.end_time = log.start_time + timedelta(minutes=max_age_minutes)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
        else:
            self._invalidate_activity_cache()

    def _normalize_datetime(self, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None

            upper_value = value.upper()
            if upper_value.endswith("UTC"):
                value = value[: -3].rstrip() + "+00:00"
            elif upper_value.endswith("GMT"):
                value = value[: -3].rstrip() + "+00:00"
            elif upper_value.endswith(" Z"):
                value = value[: -2] + "+00:00"
            elif value.endswith("Z"):
                value = value[:-1] + "+00:00"

            value = re.sub(r"([+-]\d{2})(\d{2})(?!:|\d)", r"\1:\2", value)
            if re.search(r"[+-]\d{2}$", value):
                value += ":00"

            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            value = parsed
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            return value
        return None

    def _aggregate_activity_logs(self) -> dict:
        rows = (
            self.db.query(
                cast(UserActivityLog.start_time, String).label("start_time"),
                cast(UserActivityLog.end_time, String).label("end_time"),
                UserActivityLog.capsule_id,
                Capsule.title,
                Capsule.domain,
                Capsule.area,
            )
            .outerjoin(Capsule, Capsule.id == UserActivityLog.capsule_id)
            .filter(UserActivityLog.user_id == self.user_id)
            .all()
        )

        total_seconds = 0.0
        total_sessions = 0
        domain_totals: dict[str, float] = {}
        area_totals: dict[tuple[str, str], float] = {}
        capsule_totals: dict[int | str, dict[str, object]] = {}
        day_set: set = set()

        now = datetime.utcnow()

        for row in rows:
            start = self._normalize_datetime(row.start_time)
            end = self._normalize_datetime(row.end_time) or now
            if not start or end < start:
                continue

            seconds = (end - start).total_seconds()
            if seconds <= 0:
                continue

            total_seconds += seconds
            total_sessions += 1

            domain = row.domain or "autres"
            area = row.area or "général"

            domain_totals[domain] = domain_totals.get(domain, 0.0) + seconds
            area_totals[(domain, area)] = area_totals.get((domain, area), 0.0) + seconds

            capsule_key = row.capsule_id if row.capsule_id is not None else f"uncategorized-{area}"
            if capsule_key not in capsule_totals:
                capsule_totals[capsule_key] = {
                    "capsule_id": row.capsule_id,
                    "title": row.title or "Session libre",
                    "domain": domain,
                    "area": area,
                    "seconds": 0,
                }
            capsule_totals[capsule_key]["seconds"] += seconds

            current_day = start.date()
            last_day = end.date()
            while current_day <= last_day:
                day_set.add(current_day)
                current_day += timedelta(days=1)

        # Fallback : si aucune session n'est enregistrée (anciennes données),
        # on estime le temps passé via les complétions d'atoms.
        if total_sessions == 0 and total_seconds == 0:
            completion_rows = (
                self.db.query(
                    UserAtomProgress.completed_at,
                    Capsule.id,
                    Capsule.title,
                    Capsule.domain,
                    Capsule.area,
                )
                .join(Atom, Atom.id == UserAtomProgress.atom_id)
                .join(Molecule, Molecule.id == Atom.molecule_id)
                .join(Granule, Granule.id == Molecule.granule_id)
                .join(Capsule, Capsule.id == Granule.capsule_id)
                .filter(
                    UserAtomProgress.user_id == self.user_id,
                    UserAtomProgress.status == 'completed',
                    UserAtomProgress.completed_at.isnot(None),
                )
                .all()
            )

            fallback_seconds_per_completion = 300  # 5 minutes par activité complétée
            for completion in completion_rows:
                completed_at = self._normalize_datetime(completion.completed_at)
                if not completed_at:
                    continue

                seconds = fallback_seconds_per_completion
                total_seconds += seconds
                total_sessions += 1

                domain = completion.domain or "autres"
                area = completion.area or "général"

                domain_totals[domain] = domain_totals.get(domain, 0.0) + seconds
                area_totals[(domain, area)] = area_totals.get((domain, area), 0.0) + seconds

                capsule_key = completion.id if completion.id is not None else f"uncategorized-{area}"
                if capsule_key not in capsule_totals:
                    capsule_totals[capsule_key] = {
                        "capsule_id": completion.id,
                        "title": completion.title or "Session libre",
                        "domain": domain,
                        "area": area,
                        "seconds": 0,
                    }
                capsule_totals[capsule_key]["seconds"] += seconds

                day_set.add(completed_at.date())

        domain_breakdown = [
            {"domain": domain, "seconds": int(seconds)}
            for domain, seconds in sorted(domain_totals.items(), key=lambda item: item[1], reverse=True)
        ]
        area_breakdown = [
            {"domain": domain, "area": area, "seconds": int(seconds)}
            for (domain, area), seconds in sorted(area_totals.items(), key=lambda item: item[1], reverse=True)
        ]
        capsule_breakdown = [
            {**entry, "seconds": int(entry["seconds"])}
            for entry in capsule_totals.values()
        ]
        capsule_breakdown.sort(key=lambda item: item["seconds"], reverse=True)

        return {
            "total_seconds": int(total_seconds),
            "total_sessions": int(total_sessions),
            "by_domain": domain_breakdown,
            "by_area": area_breakdown,
            "by_capsule": capsule_breakdown,
            "days": sorted(day_set),
        }

    def _get_activity_aggregates(self) -> dict:
        if self._activity_cache is None:
            self._activity_cache = self._aggregate_activity_logs()
        return self._activity_cache

    def get_study_breakdown(self) -> dict:
        aggregates = self._get_activity_aggregates()
        return {
            "by_domain": aggregates["by_domain"],
            "by_area": aggregates["by_area"],
            "by_capsule": aggregates["by_capsule"],
            "total_sessions": aggregates["total_sessions"],
        }

    def start_activity(self, capsule_id: int, atom_id: int) -> int:
        """Démarre le suivi d'une activité et retourne l'ID du log."""
        new_log = UserActivityLog(
            user_id=self.user_id,
            capsule_id=capsule_id,
            atom_id=atom_id
        )
        self.db.add(new_log)
        self.db.commit()
        self.db.refresh(new_log)
        self._invalidate_activity_cache()
        return new_log.id

    def end_activity(self, log_id: int):
        """Marque la fin d'une activité."""
        log_entry = self.db.query(UserActivityLog).get(log_id)
        if log_entry and log_entry.user_id == self.user_id and not log_entry.end_time:
            log_entry.end_time = datetime.utcnow()
            self.db.commit()
            self._invalidate_activity_cache()

    def get_user_stats(self):
        """Calcule et retourne les statistiques aggrégées pour l'utilisateur."""
        self._close_stale_activity_logs()
        aggregates = self._get_activity_aggregates()
        study_time_seconds = aggregates["total_seconds"]
        current_streak = self._calculate_current_streak(aggregates["days"])
        breakdown = self.get_study_breakdown()

        return {
            "total_study_time_seconds": study_time_seconds,
            "current_streak_days": current_streak,
            "total_sessions": aggregates["total_sessions"],
            "breakdown": {
                "by_domain": breakdown.get("by_domain", []),
                "by_area": breakdown.get("by_area", []),
                "by_capsule": breakdown.get("by_capsule", []),
            },
        }

    def _calculate_total_study_time(self) -> int:
        return self._get_activity_aggregates()["total_seconds"]

    def _last_login_date(self) -> date | None:
        if not self.user or not self.user.last_login_at:
            return None

        last_login = self._normalize_datetime(self.user.last_login_at)
        if not last_login:
            return None

        return last_login.date()

    def _login_streak_fallback(self) -> int:
        last_login_date = self._last_login_date()
        if not last_login_date:
            return 0

        today = datetime.utcnow().date()
        if last_login_date > today:
            return 0

        # Un utilisateur ayant déjà ouvert une session doit être compté comme ayant au moins 1 jour de streak.
        return 1

    def _calculate_current_streak(self, activity_days: list | None = None) -> int:
        if activity_days is None:
            activity_days = self._get_activity_aggregates()["days"]

        fallback_streak = self._login_streak_fallback()
        if not activity_days:
            return fallback_streak

        day_set: set[date] = set()
        for day in activity_days:
            if isinstance(day, datetime):
                day_set.add(day.date())
            else:
                day_set.add(day)

        last_login_date = self._last_login_date()
        if last_login_date:
            day_set.add(last_login_date)

        if not day_set:
            return fallback_streak

        today = datetime.utcnow().date()

        if today in day_set:
            current_day = today
        elif (today - timedelta(days=1)) in day_set:
            current_day = today - timedelta(days=1)
        else:
            return fallback_streak

        streak = 0
        while current_day in day_set:
            streak += 1
            current_day -= timedelta(days=1)

        return max(streak, fallback_streak)
    
    def record_atom_completion(self, atom_id: int) -> UserCapsuleProgress:
        """
        Enregistre la complétion d'un atome et met à jour l'XP de l'utilisateur.
        """
        logger.info(f"--- [PROGRESS] Enregistrement de l'atome ID:{atom_id} pour l'utilisateur ID:{self.user_id} ---")
        
        atom = self.db.query(Atom).get(atom_id)
        if not atom:
            raise ValueError("Atome non trouvé.")

        molecule = atom.molecule
        granule = molecule.granule
        capsule = granule.capsule
        
        # Vérifier si l'atome n'a pas déjà été validé (évite le farm d'XP)
        progress = (
            self.db.query(UserCapsuleProgress)
            .filter_by(user_id=self.user_id, capsule_id=capsule.id)
            .first()
        )
        if not progress:
            progress = UserCapsuleProgress(user_id=self.user_id, capsule_id=capsule.id, skill_id=1)
            self.db.add(progress)

        atom_progress = (
            self.db.query(UserAtomProgress)
            .filter_by(user_id=self.user_id, atom_id=atom_id)
            .first()
        )
        if not atom_progress:
            atom_progress = UserAtomProgress(user_id=self.user_id, atom_id=atom_id)
            self.db.add(atom_progress)

        if progress.xp is None:
            progress.xp = 0

        if not atom_progress.xp_awarded:
            xp_to_award = self._calculate_xp_for_atom(capsule, molecule, atom)
            xp_delta = 0

            if getattr(atom, "is_bonus", False):
                progress.bonus_xp = (progress.bonus_xp or 0) + xp_to_award
                xp_delta = xp_to_award
            else:
                remaining = max(0, TOTAL_XP - (progress.xp or 0))
                xp_delta = min(xp_to_award, remaining)
                progress.xp = (progress.xp or 0) + xp_delta

            atom_progress.xp_awarded = True
            atom_progress.completed_at = datetime.utcnow()
            atom_progress.status = 'completed'
            self.db.commit()
            self.db.refresh(progress)
            self._invalidate_activity_cache()
            logger.info(
                "--- [PROGRESS] +%s XP accordés (%s). Total noyau: %s | Bonus: %s ---",
                xp_delta,
                "bonus" if getattr(atom, "is_bonus", False) else "noyau",
                progress.xp,
                getattr(progress, "bonus_xp", 0),
            )
            # Badges liés à la complétion
            try:
                badge_crud.award_badge(self.db, self.user_id, "explorateur-premiere-lecon")
                # Seuils multi-leçons
                total_completed = (
                    self.db.query(UserAtomProgress)
                    .filter(
                        UserAtomProgress.user_id == self.user_id,
                        UserAtomProgress.status == 'completed'
                    )
                    .count()
                )
                if total_completed >= 10:
                    badge_crud.award_badge(self.db, self.user_id, "explorateur-dix-lecons")
                if total_completed >= 50:
                    badge_crud.award_badge(self.db, self.user_id, "explorateur-cinquante-lecons")
            except Exception:
                pass
        else:
            # assurer statut cohérent même sans nouvel XP
            atom_progress.status = 'completed'
            if not atom_progress.completed_at:
                atom_progress.completed_at = datetime.utcnow()
            self.db.commit()
            self._invalidate_activity_cache()

        return progress

    def _calculate_xp_for_atom(self, capsule: Capsule, molecule: Molecule, atom: Atom) -> int:
        atom_xp_map, _ = calculate_capsule_xp_distribution(capsule)
        return atom_xp_map.get(atom.id, 0)
