from types import SimpleNamespace

import pytest
import stripe
from fastapi import HTTPException

from app.api.v2.endpoints import user_router, stripe_router
from app.schemas.user.user_schema import UserUpdate
from app.models.user.user_model import SubscriptionStatus
from tests.utils import create_user


@pytest.mark.asyncio
async def test_update_me_updates_core_fields(monkeypatch, db_session):
    user = create_user(
        db_session,
        username="oldname",
        email="old@example.com",
        full_name=None,
        is_email_verified=True,
    )

    async def fake_send_confirm_email(db, user_obj, lang):
        fake_send_confirm_email.called = (db, user_obj, lang)

    fake_send_confirm_email.called = None
    monkeypatch.setattr(user_router, "send_confirm_email", fake_send_confirm_email)

    payload = UserUpdate(
        email="new@example.com",
        username="newname",
        full_name="  New Full Name  ",
    )
    request = SimpleNamespace(headers={})

    updated_user = await user_router.update_me(payload, request, db_session, user)

    assert updated_user.email == "new@example.com"
    assert updated_user.username == "newname"
    assert updated_user.full_name == "New Full Name"
    assert updated_user.is_email_verified is False
    assert fake_send_confirm_email.called is not None


@pytest.mark.asyncio
async def test_update_me_updates_profile_customization(db_session):
    user = create_user(
        db_session,
        username="profiled",
        email="profiled@example.com",
        active_title=None,
        profile_border_color=None,
    )

    payload = UserUpdate(
        active_title="  Explorateur  ",
        profile_border_color="  #123abc  ",
    )

    request = SimpleNamespace(headers={})

    updated_user = await user_router.update_me(payload, request, db_session, user)

    assert updated_user.active_title == "Explorateur"
    assert updated_user.profile_border_color == "#123abc"

    # Mettre à jour une deuxième fois pour vérifier la suppression
    payload = UserUpdate(active_title="  ", profile_border_color="  ")
    updated_user = await user_router.update_me(payload, request, db_session, user)

    assert updated_user.active_title is None
    assert updated_user.profile_border_color is None


@pytest.mark.asyncio
async def test_update_me_prevents_duplicate_email(monkeypatch, db_session):
    user = create_user(
        db_session,
        username="primary",
        email="primary@example.com",
        full_name="User",
        is_email_verified=True,
    )
    other = create_user(
        db_session,
        username="other",
        email="duplicate@example.com",
        full_name="Other",
        is_email_verified=True,
    )

    async def fake_send_confirm_email(*args, **kwargs):  # pragma: no cover - ne doit pas être appelé
        raise AssertionError("send_confirm_email should not be called")

    monkeypatch.setattr(user_router, "send_confirm_email", fake_send_confirm_email)

    request = SimpleNamespace(headers={})
    payload = UserUpdate(email="duplicate@example.com")

    with pytest.raises(HTTPException) as exc:
        await user_router.update_me(payload, request, db_session, user)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Email already registered"

    db_session.refresh(user)
    assert user.email == "primary@example.com"


@pytest.mark.asyncio
async def test_cancel_subscription_revokes_premium(monkeypatch, db_session):
    user = create_user(
        db_session,
        username="premium",
        email="premium@example.com",
        subscription_status=SubscriptionStatus.PREMIUM,
        stripe_customer_id="cus_123",
        active_title="Membre Premium",
        profile_border_color="#FFD700",
    )

    class FakeList:
        def __init__(self):
            self.data = [{"id": "sub_1", "status": "active"}]

    def fake_list(**kwargs):
        return FakeList()

    canceled = []

    def fake_delete(sub_id):
        canceled.append(sub_id)
        return {"id": sub_id, "status": "canceled"}

    monkeypatch.setattr(stripe.Subscription, "list", fake_list)
    monkeypatch.setattr(stripe.Subscription, "delete", fake_delete)

    result = await stripe_router.cancel_subscription(current_user=user, db=db_session)

    assert result == {"status": "canceled", "canceled_subscriptions": ["sub_1"]}

    db_session.refresh(user)
    assert user.subscription_status == SubscriptionStatus.CANCELED
    assert user.active_title is None
    assert user.profile_border_color is None


@pytest.mark.asyncio
async def test_schedule_account_deletion_marks_user(monkeypatch, db_session):
    user = create_user(
        db_session,
        username="deleteme",
        email="delete@example.com",
        subscription_status=SubscriptionStatus.PREMIUM,
        stripe_customer_id="cus_del",
        active_title="Membre Premium",
        profile_border_color="#FFD700",
    )

    monkeypatch.setattr(
        stripe_router,
        "_cancel_active_subscriptions_for_customer",
        lambda customer_id: ["sub_del"] if customer_id == "cus_del" else [],
    )

    result = await user_router.schedule_account_deletion(db_session, user)

    assert result["status"] == "scheduled"
    assert result["canceled_stripe_subscriptions"] == ["sub_del"]

    db_session.refresh(user)
    assert user.is_active is False
    assert user.subscription_status == SubscriptionStatus.CANCELED
    assert user.account_deletion_requested_at is not None
    assert user.account_deletion_scheduled_at is not None
    assert (user.account_deletion_scheduled_at - user.account_deletion_requested_at).days == 30
