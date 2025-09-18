import stripe
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.v2.dependencies import get_db, get_current_user
from app.models.user.user_model import User, SubscriptionStatus
from app.crud import user_crud, badge_crud

router = APIRouter()
stripe.api_key = settings.STRIPE_SECRET_KEY

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

    # Gère les différents types d'événements
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = session.get('customer')
        user = user_crud.get_user_by_stripe_id(db, stripe_id=customer_id)
        if user:
            # On met à jour le statut
            user.subscription_status = SubscriptionStatus.PREMIUM
            db.commit()
            print(f"✅ Abonnement PREMIUM activé pour l'utilisateur {user.id}")

            # --- AJOUTEZ CES LIGNES POUR ATTRIBUER LE BADGE ---
            # On attribue le badge, ce qui déclenchera la notification et le toast !
            badge_crud.award_badge(db, user_id=user.id, badge_slug="premium-subscriber")
            
            # On peut aussi définir le titre et la couleur par défaut ici
            user.active_title = "Membre Premium"
            user.profile_border_color = "#FFD700" # Une couleur dorée
            db.commit()
            print(f"🏆 Badge Premium et titre attribués à l'utilisateur {user.id}")


    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        user = user_crud.get_user_by_stripe_id(db, stripe_id=customer_id)
        if user:
            user.active_title = None
            user.profile_border_color = None
            user.subscription_status = SubscriptionStatus.CANCELED
            db.commit()
            print(f"❌ Abonnement CANCELED pour l'utilisateur {user.id}")

    return {"status": "success"}