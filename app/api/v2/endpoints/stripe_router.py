import logging
from typing import Any, Dict, Optional

import stripe
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User, SubscriptionStatus
from app.models.user.badge_model import Badge
from app.crud import user_crud, badge_crud

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

PREMIUM_BADGE_SLUG = "premium-subscriber"
PREMIUM_BADGE_NAME = "Abonné Premium"
PREMIUM_BADGE_DESCRIPTION = "Un abonnement premium est actif sur ce compte."
PREMIUM_BADGE_ICON = "crown"
PREMIUM_BADGE_CATEGORY = "Premium"
PREMIUM_BADGE_POINTS = 50
PREMIUM_TITLE = "Membre Premium"
PREMIUM_BORDER_COLOR = "#FFD700"  # Couleur dorée

ACTIVE_SUBSCRIPTION_STATUSES = {"trialing", "active", "past_due", "unpaid"}


def _ensure_premium_badge_exists(db: Session) -> None:
    """Garantit que le badge premium est présent en base pour l'attribution."""

    badge = db.query(Badge).filter(Badge.slug == PREMIUM_BADGE_SLUG).first()
    if badge:
        return

    badge = Badge(
        name=PREMIUM_BADGE_NAME,
        slug=PREMIUM_BADGE_SLUG,
        description=PREMIUM_BADGE_DESCRIPTION,
        icon=PREMIUM_BADGE_ICON,
        category=PREMIUM_BADGE_CATEGORY,
        points=PREMIUM_BADGE_POINTS,
    )
    db.add(badge)
    db.flush()
    logger.info("Création du badge premium manquant (%s)", PREMIUM_BADGE_SLUG)


def _activate_premium_for_user(db: Session, user: Optional[User]) -> None:
    """Attribue le statut premium, le titre/bordure et le badge à l'utilisateur."""

    if not user:
        logger.warning("Webhook Stripe ignoré: utilisateur introuvable pour l'activation premium.")
        return

    updated = False
    if user.subscription_status != SubscriptionStatus.PREMIUM:
        user.subscription_status = SubscriptionStatus.PREMIUM
        updated = True

    if user.active_title != PREMIUM_TITLE:
        user.active_title = PREMIUM_TITLE
        updated = True

    if user.profile_border_color != PREMIUM_BORDER_COLOR:
        user.profile_border_color = PREMIUM_BORDER_COLOR
        updated = True

    if updated:
        db.commit()
        db.refresh(user)
        logger.info("✅ Statut PREMIUM activé pour l'utilisateur %s", user.id)

    _ensure_premium_badge_exists(db)

    try:
        awarded_badge = badge_crud.award_badge(db, user_id=user.id, badge_slug=PREMIUM_BADGE_SLUG)
        if awarded_badge is None:
            logger.warning(
                "Impossible d'attribuer le badge premium à l'utilisateur %s: badge introuvable.",
                user.id,
            )
    except Exception as exc:  # pragma: no cover - sécurité supplémentaire
        logger.warning("Impossible d'attribuer le badge premium à l'utilisateur %s: %s", user.id, exc)


def _set_subscription_to_canceled(db: Session, user: Optional[User]) -> None:
    if not user:
        logger.warning("Webhook Stripe ignoré: utilisateur introuvable pour l'annulation d'abonnement.")
        return

    updated = False
    if user.active_title is not None:
        user.active_title = None
        updated = True

    if user.profile_border_color is not None:
        user.profile_border_color = None
        updated = True

    if user.subscription_status != SubscriptionStatus.CANCELED:
        user.subscription_status = SubscriptionStatus.CANCELED
        updated = True

    if updated:
        db.commit()
        db.refresh(user)
        logger.info("❌ Abonnement CANCELED pour l'utilisateur %s", user.id)

# --- Helpers Stripe -------------------------------------------------------

def _cancel_active_subscriptions_for_customer(customer_id: Optional[str]) -> list[str]:
    """Annule toutes les souscriptions Stripe actives pour un client donné."""

    if not customer_id:
        return []

    canceled_ids: list[str] = []
    subscriptions = stripe.Subscription.list(customer=customer_id, status="all", limit=100)

    data = getattr(subscriptions, "data", None)
    if data is None and isinstance(subscriptions, dict):  # pragma: no cover - support tests
        data = subscriptions.get("data", [])

    for subscription in data or []:
        status = subscription.get("status")
        sub_id = subscription.get("id")
        if status in ACTIVE_SUBSCRIPTION_STATUSES and sub_id:
            stripe.Subscription.delete(sub_id)
            canceled_ids.append(sub_id)

    return canceled_ids


def _parse_user_id(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning("Impossible de convertir la valeur '%s' en identifiant utilisateur.", value)
        return None


def _extract_user_id_from_metadata(metadata: Dict[str, Any] | None) -> Optional[int]:
    if not metadata:
        return None
    for key in ("user_id", "userId", "user-id"):
        user_id = _parse_user_id(metadata.get(key))
        if user_id is not None:
            return user_id
    return None


def _link_customer_to_user(db: Session, user: User | None, customer_id: Optional[str]) -> None:
    if not user or not customer_id:
        return

    if user.stripe_customer_id == customer_id:
        return

    if user.stripe_customer_id and user.stripe_customer_id != customer_id:
        logger.warning(
            "Utilisateur %s déjà associé au client Stripe %s (reçu %s)",
            user.id,
            user.stripe_customer_id,
            customer_id,
        )
        return

    user.stripe_customer_id = customer_id
    db.commit()
    db.refresh(user)
    logger.info("Association du client Stripe %s à l'utilisateur %s", customer_id, user.id)


def _find_user_for_event(
    db: Session,
    *,
    customer_id: Optional[str],
    metadata: Dict[str, Any] | None = None,
    client_reference_id: Optional[str] = None,
    customer_email: Optional[str] = None,
) -> Optional[User]:
    if customer_id:
        user = user_crud.get_user_by_stripe_id(db, stripe_id=customer_id)
        if user:
            return user

    metadata_dict: Dict[str, Any] | None = dict(metadata) if metadata else None
    user_id = _extract_user_id_from_metadata(metadata_dict)

    if user_id is None and client_reference_id:
        user_id = _parse_user_id(client_reference_id)

    if user_id is not None:
        user = db.get(User, user_id)
        if user:
            _link_customer_to_user(db, user, customer_id)
            return user

    if customer_email:
        user = user_crud.get_user_by_email(db, email=customer_email)
        if user:
            _link_customer_to_user(db, user, customer_id)
            return user

    logger.warning(
        "Impossible de faire correspondre l'événement Stripe (customer=%s, email=%s) à un utilisateur.",
        customer_id,
        customer_email,
    )
    return None


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permet à l'utilisateur connecté d'annuler son abonnement Stripe en cours."""

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="stripe_not_configured")

    if not current_user.stripe_customer_id:
        _set_subscription_to_canceled(db, current_user)
        return {"status": "already_canceled", "canceled_subscriptions": []}

    try:
        canceled_ids = _cancel_active_subscriptions_for_customer(current_user.stripe_customer_id)
    except stripe.error.StripeError as exc:
        logger.error(
            "Stripe cancellation error for user %s (customer %s): %s",
            current_user.id,
            current_user.stripe_customer_id,
            exc,
        )
        raise HTTPException(status_code=502, detail="stripe_cancellation_failed") from exc

    _set_subscription_to_canceled(db, current_user)

    status_value = "canceled" if canceled_ids else "already_canceled"
    return {"status": status_value, "canceled_subscriptions": canceled_ids}


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crée une session de paiement Stripe pour l'utilisateur actuel."""
    
    # Crée un client Stripe pour l'utilisateur s'il n'en a pas déjà un
    if not current_user.stripe_customer_id:
        customer = stripe.Customer.create(email=current_user.email, name=current_user.username)
        current_user.stripe_customer_id = customer.id
        db.commit()
        db.refresh(current_user)

    try:
        metadata = {"user_id": str(current_user.id)}
        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': settings.STRIPE_PREMIUM_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
            client_reference_id=str(current_user.id),
            metadata=metadata,
            subscription_data={"metadata": metadata},
            # --- ON MODIFIE L'URL DE SUCCÈS ICI ---
            success_url=f"http://localhost:5173/payment-success", # Nouvelle URL
            cancel_url=f"http://localhost:5173/premium", # On retourne à la page premium en cas d'annulation
        )
        return {"sessionId": checkout_session.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Écoute les événements de Stripe pour mettre à jour la BDD."""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event.get('type')
    logger.info("Réception webhook Stripe: %s", event_type)

    if event_type == 'checkout.session.completed':
        session_data = event['data']['object']
        customer_details = session_data.get('customer_details') or {}
        user = _find_user_for_event(
            db,
            customer_id=session_data.get('customer'),
            metadata=session_data.get('metadata'),
            client_reference_id=session_data.get('client_reference_id'),
            customer_email=customer_details.get('email'),
        )
        _activate_premium_for_user(db, user)

    elif event_type in {'invoice.payment_succeeded', 'invoice.paid'}:
        invoice = event['data']['object']
        user = _find_user_for_event(
            db,
            customer_id=invoice.get('customer'),
            metadata=invoice.get('metadata'),
            customer_email=invoice.get('customer_email'),
        )
        _activate_premium_for_user(db, user)

    elif event_type in {'customer.subscription.created', 'customer.subscription.updated'}:
        subscription = event['data']['object']
        user = _find_user_for_event(
            db,
            customer_id=subscription.get('customer'),
            metadata=subscription.get('metadata'),
        )
        status = subscription.get('status')

        if status in {'active', 'trialing'}:
            _activate_premium_for_user(db, user)
        elif status in {'canceled', 'incomplete_expired', 'unpaid', 'paused'}:
            _set_subscription_to_canceled(db, user)

    elif event_type == 'customer.subscription.deleted':
        subscription = event['data']['object']
        user = _find_user_for_event(
            db,
            customer_id=subscription.get('customer'),
            metadata=subscription.get('metadata'),
        )
        _set_subscription_to_canceled(db, user)

    return {"status": "success"}
