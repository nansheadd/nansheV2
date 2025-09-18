"""
Définition centralisée des règles de badges (récompenses, titres, triggers).

Objectif: rester modulaire sans changer le schéma SQL.
 - Les métadonnées (reward_xp, title) sont définies ici.
 - Le descriptif visuel (name, description, category, points, icon) reste dans la BDD (seeds).

On peut ajouter/éditer facilement de nouveaux badges en étendant ce mapping.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict


@dataclass(frozen=True)
class BadgeRule:
    # Points d'XP accordés au moment du déverrouillage (ajoutés à user.xp_points)
    reward_xp: int = 0
    # Titre honorifique accordé (non persisté côté User tant qu'on n'a pas de champ dédié)
    grants_title: Optional[str] = None


# Règles par slug (les slugs doivent exister dans la table badges via seeds, sauf badges dynamiques)
BADGE_RULES: Dict[str, BadgeRule] = {
    # Onboarding
    "initiation-inscription": BadgeRule(reward_xp=25, grants_title="Nouveau venu"),
    "voyageur-premiere-connexion": BadgeRule(reward_xp=15),
    "initiation-premiere-notification": BadgeRule(reward_xp=10),
    "initiation-profil-complet": BadgeRule(reward_xp=40, grants_title="Profil accompli"),

    # Exploration / Progression
    "explorateur-premiere-lecon": BadgeRule(reward_xp=30),
    "explorateur-dix-lecons": BadgeRule(reward_xp=120, grants_title="Explorateur"),
    "explorateur-cinquante-lecons": BadgeRule(reward_xp=400, grants_title="Marathonien"),

    # Capsules (création / inscription)
    "artisan-premiere-capsule": BadgeRule(reward_xp=50, grants_title="Artisan"),
    "artisan-cinq-capsules": BadgeRule(reward_xp=200, grants_title="Architecte"),
    "apprenant-premiere-inscription-capsule": BadgeRule(reward_xp=25),

    # Collection
    "collection-dix-badges": BadgeRule(reward_xp=100),

    # Premium
    "premium-subscriber": BadgeRule(reward_xp=150, grants_title="Membre Premium"),
}


def compute_profile_completeness(*, has_full_name: bool, enrolled_count: int) -> int:
    """Calcule un pourcentage simple de complétion de profil (sans nouveau champ DB).

    - 60% si le nom complet est renseigné
    - +40% si l'utilisateur est inscrit à au moins une capsule
    """
    score = 0
    if has_full_name:
        score += 60
    if enrolled_count > 0:
        score += 40
    return min(score, 100)

