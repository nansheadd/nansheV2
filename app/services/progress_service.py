import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta
from app.models.capsule.utility_models import UserCapsuleProgress
from app.models.progress.user_activity_log_model import UserActivityLog
from app.models.user.user_model import User  # <-- Import the User model
from app.models.progress.user_atomic_progress import UserAtomProgress

from app.models.capsule.atom_model import Atom
from app.crud import badge_crud
from app.models.progress.user_atomic_progress import UserAtomProgress

logger = logging.getLogger(__name__)

# Le barème d'XP que vous avez fourni. Facile à mettre à jour ici.
XP_PER_LEVEL = {
    1: 820, 2: 890, 3: 960, 4: 1030, 5: 1120, 6: 1210, 7: 1300, 8: 1410,
    9: 1520, 10: 1640, 11: 1770, 12: 1910, 13: 2070, 14: 2230, 15: 2410,
    16: 2600, 17: 2810, 18: 3040, 19: 3280, 20: 3540, 21: 3830, 22: 4130,
    23: 4460, 24: 4820, 25: 5200
}

TOTAL_XP = 60000

class ProgressService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        # Fetch the user and assign it to self.user
        self.user = self.db.query(User).get(self.user_id)

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
        return new_log.id

    def end_activity(self, log_id: int):
        """Marque la fin d'une activité."""
        log_entry = self.db.query(UserActivityLog).get(log_id)
        if log_entry and log_entry.user_id == self.user_id and not log_entry.end_time:
            log_entry.end_time = datetime.utcnow()
            self.db.commit()

    def get_user_stats(self):
        """Calcule et retourne les statistiques aggrégées pour l'utilisateur."""
        study_time_seconds = self._calculate_total_study_time()
        current_streak = self._calculate_current_streak()

        return {
            "total_study_time_seconds": study_time_seconds,
            "current_streak_days": current_streak
        }
    
    def _calculate_total_study_time(self) -> int:
        """
        Calcule le temps d'étude total en secondes.
        Utilise EXTRACT(EPOCH FROM ...) pour la compatibilité avec PostgreSQL.
        """
        if not self.user:
            return 0

        # On calcule la différence entre les timestamps en secondes
        # et on fait la somme de toutes ces durées.
        duration = func.extract('epoch', UserActivityLog.end_time) - func.extract('epoch', UserActivityLog.start_time)
        
        total_seconds = self.db.query(func.sum(duration)).filter(
            UserActivityLog.user_id == self.user_id, # <-- Use self.user_id directly
            UserActivityLog.end_time.isnot(None)
        ).scalar()

        return int(total_seconds) if total_seconds else 0
    
    def _calculate_current_streak(self) -> int:
        """Calcule le nombre de jours consécutifs d'activité."""
        # Récupère les jours uniques d'activité, sans les heures
        activity_days_query = self.db.query(
            cast(UserActivityLog.start_time, Date).label('activity_date')
        ).filter(UserActivityLog.user_id == self.user_id).distinct().order_by(cast(UserActivityLog.start_time, Date).desc())
        
        activity_days = [row.activity_date for row in activity_days_query.all()]
        if not activity_days:
            return 0

        streak = 0
        today = datetime.utcnow().date()
        
        # Si la dernière activité n'est ni aujourd'hui ni hier, le streak est de 0
        if (today - activity_days[0]).days > 1:
            return 0
            
        # On compte les jours consécutifs en partant d'aujourd'hui
        expected_day = today if activity_days[0] == today else today - timedelta(days=1)
        
        for day in activity_days:
            if day == expected_day:
                streak += 1
                expected_day -= timedelta(days=1)
            else:
                break
                
        return streak
    
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

        if not atom_progress.xp_awarded:
            xp_to_award = self._calculate_xp_for_atom(granule.order, len(molecule.atoms))
            progress.xp = (progress.xp or 0) + xp_to_award
            atom_progress.xp_awarded = True
            atom_progress.completed_at = datetime.utcnow()
            atom_progress.status = 'completed'
            self.db.commit()
            self.db.refresh(progress)
            logger.info(
                "--- [PROGRESS] +%s XP accordés. Total pour la capsule: %s XP ---",
                xp_to_award,
                progress.xp,
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

        return progress

    def _calculate_xp_for_atom(self, level_order: int, num_atoms_in_molecule: int) -> int:
        """
        Calcule la valeur en XP d'un atome en divisant l'XP du niveau par le nombre d'atomes.
        """
        total_xp_for_level = XP_PER_LEVEL.get(level_order, 0)
        if num_atoms_in_molecule == 0:
            return 0
        
        # On arrondit à l'entier le plus proche
        return round(total_xp_for_level / num_atoms_in_molecule)
