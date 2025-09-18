from datetime import datetime
from typing import List, Dict, Optional

from sqlalchemy.orm import Session

from app.models.user.badge_model import Badge, UserBadge
from app.schemas.user.badge_schema import BadgeRead, BadgeWithStatus
from app.notifications.websocket_manager import notification_ws_manager
from app.crud import notification_crud
from app.schemas.user.notification_schema import NotificationCreate
from app.models.user.notification_model import NotificationCategory
from app.models.user.user_model import User
from app.gamification.badge_rules import BADGE_RULES


def get_badges_with_status(db: Session, user_id: int) -> List[BadgeWithStatus]:
    badges = db.query(Badge).order_by(Badge.category, Badge.points, Badge.id).all()
    user_badges = (
        db.query(UserBadge)
        .filter(UserBadge.user_id == user_id)
        .all()
    )
    awarded_map = {ub.badge_id: ub.awarded_at for ub in user_badges}

    result: List[BadgeWithStatus] = []
    for badge in badges:
        result.append(
            BadgeWithStatus(
                badge=BadgeRead.model_validate(badge),
                is_unlocked=badge.id in awarded_map,
                awarded_at=awarded_map.get(badge.id),
            )
        )
    return result


def award_badge(db: Session, user_id: int, badge_slug: str) -> Optional[UserBadge]:
    badge = db.query(Badge).filter(Badge.slug == badge_slug).first()
    if not badge:
        return None

    existing = (
        db.query(UserBadge)
        .filter(UserBadge.user_id == user_id, UserBadge.badge_id == badge.id)
        .first()
    )
    if existing:
        return existing

    user_badge = UserBadge(user_id=user_id, badge_id=badge.id)
    db.add(user_badge)
    # Appliquer récompenses (XP, titre) à l'utilisateur si défini dans les règles
    rule = BADGE_RULES.get(badge_slug)
    if rule:
        user = db.query(User).get(user_id)
        if user and rule.reward_xp:
            user.xp_points = (user.xp_points or 0) + int(rule.reward_xp)
    db.commit()
    db.refresh(user_badge)

    # Crée également une notification standard
    notification_crud.create_notification(
        db,
        NotificationCreate(
            user_id=user_id,
            title=f"Badge obtenu : {badge.name}",
            message=badge.description,
            category=NotificationCategory.BADGE,
            link="/badges",
        ),
    )

    payload = {
        "type": "badge_awarded",
        "badge": BadgeRead.model_validate(badge).model_dump(),
        "awarded_at": user_badge.awarded_at.isoformat(),
        # Métadonnées non critiques pour l'UI (pas stockées en DB)
        "reward_xp": (rule.reward_xp if rule else 0),
        "title": (rule.grants_title if rule else None),
    }
    notification_ws_manager.notify(user_id, payload)

    # Meta-badge: 10 badges débloqués
    try:
        if badge_slug != "collection-dix-badges":
            total = db.query(UserBadge).filter(UserBadge.user_id == user_id).count()
            if total >= 10:
                # Evite récursion infinie grâce au check ci-dessus
                award_badge(db, user_id, "collection-dix-badges")
    except Exception:
        pass
    return user_badge


# --- Badges dynamiques (ex: pionnier d'un domaine/area) ---
def _ensure_badge(db: Session, *, slug: str, name: str, description: str, category: str, points: int = 25, icon: Optional[str] = None) -> Badge:
    badge = db.query(Badge).filter(Badge.slug == slug).first()
    if badge:
        return badge
    badge = Badge(slug=slug, name=name, description=description, category=category, points=points, icon=icon)
    db.add(badge)
    db.commit()
    db.refresh(badge)
    return badge


def award_pioneer_for_domain(db: Session, user_id: int, domain: str) -> Optional[UserBadge]:
    slug = f"pionnier-domaine-{domain.lower()}"
    name = f"Pionnier du domaine {domain}"
    description = f"Première capsule créée dans le domaine {domain}."
    _ensure_badge(db, slug=slug, name=name, description=description, category="Pionnier", points=30, icon="trophy")
    return award_badge(db, user_id, slug)


def award_pioneer_for_area(db: Session, user_id: int, domain: str, area: str) -> Optional[UserBadge]:
    slug = f"pionnier-area-{domain.lower()}-{area.lower()}"
    name = f"Pionnier {domain}/{area}"
    description = f"Première capsule créée dans {domain}/{area}."
    _ensure_badge(db, slug=slug, name=name, description=description, category="Pionnier", points=35, icon="trophy")
    return award_badge(db, user_id, slug)
