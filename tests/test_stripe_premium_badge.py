import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("RESEND_API_KEY", "test-resend")
os.environ.setdefault("FRONTEND_BASE_URL", "http://localhost:5173")
os.environ.setdefault("BACKEND_BASE_URL", "http://localhost:8000")
os.environ.setdefault("EMAIL_FROM", "noreply@example.com")
os.environ.setdefault("SECRET_KEY", "secret-key")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test")
os.environ.setdefault("STRIPE_PREMIUM_PRICE_ID", "price_test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")

from app.api.v2.endpoints.stripe_router import (
    PREMIUM_BADGE_SLUG,
    PREMIUM_BORDER_COLOR,
    PREMIUM_TITLE,
    _activate_premium_for_user,
)
from app.models.user.user_model import SubscriptionStatus, User
from app.models.user.badge_model import Badge, UserBadge
from app.models.user.notification_model import Notification, NotificationCategory


def test_activate_premium_creates_badge_and_notification(db_session):
    user = User(username="alice", email="alice@example.com", hashed_password="hashed")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert db_session.query(Badge).filter(Badge.slug == PREMIUM_BADGE_SLUG).first() is None

    _activate_premium_for_user(db_session, user)

    db_session.refresh(user)
    assert user.subscription_status == SubscriptionStatus.PREMIUM
    assert user.active_title == PREMIUM_TITLE
    assert user.profile_border_color == PREMIUM_BORDER_COLOR

    premium_badge = db_session.query(Badge).filter(Badge.slug == PREMIUM_BADGE_SLUG).one()
    user_badge = (
        db_session.query(UserBadge)
        .filter(UserBadge.user_id == user.id, UserBadge.badge_id == premium_badge.id)
        .one()
    )
    assert user_badge is not None

    notifications = db_session.query(Notification).filter(Notification.user_id == user.id).all()
    assert len(notifications) == 1
    notification = notifications[0]
    assert notification.category == NotificationCategory.BADGE
    assert premium_badge.name in notification.title
    assert premium_badge.description == notification.message
