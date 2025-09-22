"""Persistence helpers for the coach IA energy system."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.toolbox.coach_energy_model import CoachEnergyWallet
from app.models.user.user_model import SubscriptionStatus, User


class EnergyStatus(TypedDict):
    current: float
    max: float
    percentage: float
    is_unlimited: bool
    message_cost: float
    seconds_until_full: int | None
    seconds_until_next_message: int | None
    next_message_available_at: str | None


class CoachEnergyDepleted(Exception):
    """Raised when a non-premium user has no energy left to send a message."""

    def __init__(self, status: EnergyStatus):
        super().__init__("Coach energy depleted")
        self.status = status


def _now(override: datetime | None = None) -> datetime:
    return override or datetime.now(timezone.utc)


def _is_unlimited(user: User) -> bool:
    return user.is_superuser or user.subscription_status == SubscriptionStatus.PREMIUM


def _regen_rate_per_second() -> float:
    refill_minutes = max(settings.COACH_ENERGY_RECOVERY_MINUTES, 1)
    return settings.COACH_ENERGY_MAX / (refill_minutes * 60)


def _ensure_wallet(db: Session, user: User, now: datetime) -> CoachEnergyWallet:
    wallet = db.query(CoachEnergyWallet).filter_by(user_id=user.id).first()
    if wallet:
        return wallet

    wallet = CoachEnergyWallet(user_id=user.id, current_energy=settings.COACH_ENERGY_MAX, updated_at=now)
    db.add(wallet)
    db.flush()
    return wallet


def _regenerate(wallet: CoachEnergyWallet, now: datetime) -> None:
    if wallet.updated_at is None:
        wallet.updated_at = now
        wallet.current_energy = max(wallet.current_energy, 0.0)
        return

    elapsed = max((now - wallet.updated_at).total_seconds(), 0.0)
    if elapsed <= 0:
        return

    rate = _regen_rate_per_second()
    if rate <= 0:
        return

    regenerated = elapsed * rate
    if regenerated <= 0:
        return

    wallet.current_energy = min(settings.COACH_ENERGY_MAX, wallet.current_energy + regenerated)
    wallet.updated_at = now


def _compute_status(wallet: CoachEnergyWallet, now: datetime, is_unlimited: bool) -> EnergyStatus:
    max_energy = float(settings.COACH_ENERGY_MAX)
    message_cost = float(settings.COACH_ENERGY_MESSAGE_COST)

    if is_unlimited:
        return EnergyStatus(
            current=max_energy,
            max=max_energy,
            percentage=1.0,
            is_unlimited=True,
            message_cost=message_cost,
            seconds_until_full=None,
            seconds_until_next_message=None,
            next_message_available_at=None,
        )

    current = float(max(0.0, min(wallet.current_energy, max_energy)))
    rate = _regen_rate_per_second()

    missing = max_energy - current
    seconds_until_full = math.ceil(missing / rate) if rate > 0 and missing > 0 else None

    if rate > 0 and current < message_cost:
        seconds_until_next_message = math.ceil((message_cost - current) / rate)
        availability_time = now + timedelta(seconds=seconds_until_next_message)
        next_available = availability_time.isoformat()
    else:
        seconds_until_next_message = 0 if current >= message_cost else None
        next_available = now.isoformat() if seconds_until_next_message == 0 else None

    return EnergyStatus(
        current=current,
        max=max_energy,
        percentage=0.0 if max_energy == 0 else current / max_energy,
        is_unlimited=False,
        message_cost=message_cost,
        seconds_until_full=seconds_until_full,
        seconds_until_next_message=seconds_until_next_message,
        next_message_available_at=next_available,
    )


def get_energy_status(db: Session, user: User, *, now: datetime | None = None) -> EnergyStatus:
    """Return the current energy status without consuming it."""

    current_time = _now(now)
    if _is_unlimited(user):
        return EnergyStatus(
            current=float(settings.COACH_ENERGY_MAX),
            max=float(settings.COACH_ENERGY_MAX),
            percentage=1.0,
            is_unlimited=True,
            message_cost=float(settings.COACH_ENERGY_MESSAGE_COST),
            seconds_until_full=None,
            seconds_until_next_message=None,
            next_message_available_at=None,
        )

    wallet = _ensure_wallet(db, user, current_time)
    _regenerate(wallet, current_time)
    db.add(wallet)
    db.flush()
    db.commit()
    return _compute_status(wallet, current_time, False)


def consume_energy(db: Session, user: User, *, cost: float | None = None, now: datetime | None = None) -> EnergyStatus:
    """Consume coach energy for a user and return the updated status."""

    current_time = _now(now)
    if cost is None:
        cost = float(settings.COACH_ENERGY_MESSAGE_COST)

    if _is_unlimited(user):
        return EnergyStatus(
            current=float(settings.COACH_ENERGY_MAX),
            max=float(settings.COACH_ENERGY_MAX),
            percentage=1.0,
            is_unlimited=True,
            message_cost=float(cost),
            seconds_until_full=None,
            seconds_until_next_message=None,
            next_message_available_at=None,
        )

    wallet = _ensure_wallet(db, user, current_time)
    _regenerate(wallet, current_time)

    if wallet.current_energy < cost:
        status = _compute_status(wallet, current_time, False)
        raise CoachEnergyDepleted(status)

    wallet.current_energy = max(0.0, wallet.current_energy - cost)
    wallet.updated_at = current_time
    db.add(wallet)
    db.flush()
    db.commit()

    return _compute_status(wallet, current_time, False)
