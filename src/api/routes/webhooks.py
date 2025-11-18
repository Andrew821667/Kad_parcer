"""Webhook management routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_active_user
from src.api.schemas.webhook_schemas import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookTestPayload,
    WebhookUpdate,
)
from src.core.logging import get_logger
from src.storage.database.auth_models import User
from src.storage.database.base import get_db
from src.storage.database.webhook_models import Webhook, WebhookDelivery, WebhookEvent
from src.webhooks.dispatcher import WebhookDispatcher

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List all webhooks for current user."""
    result = await db.execute(
        select(Webhook).where(Webhook.user_id == current_user.id).order_by(Webhook.created_at.desc())
    )
    webhooks = result.scalars().all()
    return webhooks


@router.post("", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    webhook_data: WebhookCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create new webhook."""
    # Convert events to string values
    events = [event.value for event in webhook_data.events]

    webhook = Webhook(
        user_id=current_user.id,
        name=webhook_data.name,
        url=str(webhook_data.url),
        secret=webhook_data.secret,
        events=events,
        headers=webhook_data.headers,
        max_retries=webhook_data.max_retries,
        retry_delay=webhook_data.retry_delay,
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    logger.info(
        "webhook_created",
        webhook_id=webhook.id,
        user_id=current_user.id,
        events=events,
    )

    return webhook


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get webhook by ID."""
    result = await db.execute(
        select(Webhook).where(
            (Webhook.id == webhook_id) & (Webhook.user_id == current_user.id)
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return webhook


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: int,
    webhook_data: WebhookUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update webhook."""
    result = await db.execute(
        select(Webhook).where(
            (Webhook.id == webhook_id) & (Webhook.user_id == current_user.id)
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Update fields
    update_data = webhook_data.model_dump(exclude_unset=True)

    if "events" in update_data:
        update_data["events"] = [event.value for event in update_data["events"]]

    if "url" in update_data:
        update_data["url"] = str(update_data["url"])

    for field, value in update_data.items():
        setattr(webhook, field, value)

    await db.commit()
    await db.refresh(webhook)

    logger.info("webhook_updated", webhook_id=webhook.id, user_id=current_user.id)

    return webhook


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete webhook."""
    result = await db.execute(
        select(Webhook).where(
            (Webhook.id == webhook_id) & (Webhook.user_id == current_user.id)
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await db.delete(webhook)
    await db.commit()

    logger.info("webhook_deleted", webhook_id=webhook_id, user_id=current_user.id)


@router.post("/{webhook_id}/test", status_code=202)
async def test_webhook(
    webhook_id: int,
    test_payload: WebhookTestPayload,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Send test webhook delivery."""
    result = await db.execute(
        select(Webhook).where(
            (Webhook.id == webhook_id) & (Webhook.user_id == current_user.id)
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Create test payload
    payload = {
        "message": test_payload.message,
        "data": test_payload.data or {},
    }

    # Dispatch test event
    dispatcher = WebhookDispatcher(db)
    await dispatcher._create_delivery(
        webhook,
        WebhookEvent.TASK_STARTED,  # Use a generic test event
        payload,
    )

    logger.info("webhook_test_sent", webhook_id=webhook_id, user_id=current_user.id)

    return {"message": "Test webhook sent"}


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_webhook_deliveries(
    webhook_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List webhook delivery attempts."""
    # Verify webhook ownership
    result = await db.execute(
        select(Webhook).where(
            (Webhook.id == webhook_id) & (Webhook.user_id == current_user.id)
        )
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Get deliveries
    result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    deliveries = result.scalars().all()

    return deliveries


@router.get("/events/types", response_model=list[str])
async def list_event_types() -> Any:
    """List available webhook event types."""
    return [event.value for event in WebhookEvent]
