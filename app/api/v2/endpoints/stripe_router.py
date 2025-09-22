import logging

import stripe
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User, SubscriptionStatus
from app.crud import user_crud, badge_crud

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

PREMIUM_BADGE_SLUG = "premium-subscriber"
PREMIUM_TITLE = "Membre Premium"
PREMIUM_BORDER_COLOR = "#FFD700"  # Couleur dorée


def _activate_premium_for_user(db: Session, user: User) -> None:
    """Attribue le statut premium, le titre/bordure et le badge à l'utilisateur."""

    if not user:
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

    try:
        badge_crud.award_badge(db, user_id=user.id, badge_slug=PREMIUM_BADGE_SLUG)
    except Exception as exc:  # pragma: no cover - sécurité supplémentaire
        logger.warning("Impossible d'attribuer le badge premium à l'utilisateur %s: %s", user.id, exc)


def _set_subscription_to_canceled(db: Session, user: User) -> None:
    if not user:
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
        checkout_session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': settings.STRIPE_PREMIUM_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
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
        session = event['data']['object']
        customer_id = session.get('customer')
        if customer_id:
            user = user_crud.get_user_by_stripe_id(db, stripe_id=customer_id)
            _activate_premium_for_user(db, user)

    elif event_type in {'invoice.payment_succeeded', 'invoice.paid'}:
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        if customer_id:
            user = user_crud.get_user_by_stripe_id(db, stripe_id=customer_id)
            _activate_premium_for_user(db, user)

    elif event_type in {'customer.subscription.created', 'customer.subscription.updated'}:
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        if not customer_id:
            return {"status": "ignored"}

        user = user_crud.get_user_by_stripe_id(db, stripe_id=customer_id)
        status = subscription.get('status')

        if status in {'active', 'trialing'}:
            _activate_premium_for_user(db, user)
        elif status in {'canceled', 'incomplete_expired', 'unpaid', 'paused'}:
            _set_subscription_to_canceled(db, user)

    elif event_type == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        if customer_id:
            user = user_crud.get_user_by_stripe_id(db, stripe_id=customer_id)
            _set_subscription_to_canceled(db, user)

    return {"status": "success"}
