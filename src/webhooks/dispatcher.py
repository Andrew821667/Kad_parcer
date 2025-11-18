"""Webhook event dispatcher."""

import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.storage.database.webhook_models import Webhook, WebhookDelivery, WebhookEvent

logger = get_logger(__name__)


class WebhookDispatcher:
    """Handles webhook event dispatching and delivery."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize webhook dispatcher.

        Args:
            db: Database session
        """
        self.db = db

    async def dispatch(
        self,
        event: WebhookEvent,
        payload: dict[str, Any],
        user_id: Optional[int] = None,
    ) -> None:
        """Dispatch webhook event to all subscribed webhooks.

        Args:
            event: Event type
            payload: Event payload
            user_id: Optional user ID to filter webhooks
        """
        # Find all active webhooks subscribed to this event
        query = select(Webhook).where(
            Webhook.is_active.is_(True),
            Webhook.events.contains([event.value]),
        )

        if user_id is not None:
            query = query.where(Webhook.user_id == user_id)

        result = await self.db.execute(query)
        webhooks = result.scalars().all()

        logger.info(
            "dispatching_webhook_event",
            event=event.value,
            webhooks_count=len(webhooks),
            user_id=user_id,
        )

        # Create delivery records for each webhook
        for webhook in webhooks:
            await self._create_delivery(webhook, event, payload)

    async def _create_delivery(
        self,
        webhook: Webhook,
        event: WebhookEvent,
        payload: dict[str, Any],
    ) -> WebhookDelivery:
        """Create webhook delivery record and attempt delivery.

        Args:
            webhook: Webhook configuration
            event: Event type
            payload: Event payload

        Returns:
            WebhookDelivery record
        """
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event=event.value,
            payload=payload,
            status="pending",
            attempts=0,
        )

        self.db.add(delivery)
        await self.db.flush()

        # Attempt immediate delivery
        await self._attempt_delivery(webhook, delivery)

        await self.db.commit()
        return delivery

    async def _attempt_delivery(
        self,
        webhook: Webhook,
        delivery: WebhookDelivery,
    ) -> bool:
        """Attempt to deliver webhook.

        Args:
            webhook: Webhook configuration
            delivery: Delivery record

        Returns:
            True if successful, False otherwise
        """
        delivery.attempts += 1

        try:
            # Prepare payload
            event_payload = {
                "event": delivery.event,
                "timestamp": datetime.utcnow().isoformat(),
                "delivery_id": delivery.id,
                "data": delivery.payload,
            }

            # Prepare headers
            headers = webhook.headers.copy() if webhook.headers else {}
            headers["Content-Type"] = "application/json"
            headers["User-Agent"] = "KAD-Parser-Webhook/1.0"

            # Add signature if secret is configured
            if webhook.secret:
                signature = self._generate_signature(event_payload, webhook.secret)
                headers["X-Webhook-Signature"] = signature

            # Send webhook request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook.url,
                    json=event_payload,
                    headers=headers,
                )

                delivery.response_code = response.status_code
                delivery.response_body = response.text[:1000]  # Store first 1000 chars

                if 200 <= response.status_code < 300:
                    # Success
                    delivery.status = "success"
                    delivery.delivered_at = datetime.utcnow()

                    # Update webhook statistics
                    webhook.total_deliveries += 1
                    webhook.successful_deliveries += 1
                    webhook.last_delivery_at = datetime.utcnow()
                    webhook.last_delivery_status = "success"

                    logger.info(
                        "webhook_delivered_successfully",
                        webhook_id=webhook.id,
                        delivery_id=delivery.id,
                        event=delivery.event,
                        status_code=response.status_code,
                    )
                    return True

                # Non-success status code
                delivery.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
                await self._handle_delivery_failure(webhook, delivery)
                return False

        except httpx.RequestError as e:
            # Network error
            delivery.error_message = f"Request error: {str(e)}"
            await self._handle_delivery_failure(webhook, delivery)
            return False

        except Exception as e:
            # Unexpected error
            delivery.error_message = f"Unexpected error: {str(e)}"
            await self._handle_delivery_failure(webhook, delivery)
            logger.error(
                "webhook_delivery_error",
                webhook_id=webhook.id,
                delivery_id=delivery.id,
                error=str(e),
                exc_info=True,
            )
            return False

    async def _handle_delivery_failure(
        self,
        webhook: Webhook,
        delivery: WebhookDelivery,
    ) -> None:
        """Handle failed delivery attempt.

        Args:
            webhook: Webhook configuration
            delivery: Delivery record
        """
        if delivery.attempts < webhook.max_retries:
            # Schedule retry
            retry_delay = webhook.retry_delay * (2 ** (delivery.attempts - 1))  # Exponential backoff
            delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=retry_delay)
            delivery.status = "pending"

            logger.warning(
                "webhook_delivery_failed_will_retry",
                webhook_id=webhook.id,
                delivery_id=delivery.id,
                attempt=delivery.attempts,
                next_retry=delivery.next_retry_at.isoformat(),
            )
        else:
            # Max retries exceeded
            delivery.status = "failed"

            # Update webhook statistics
            webhook.total_deliveries += 1
            webhook.failed_deliveries += 1
            webhook.last_delivery_at = datetime.utcnow()
            webhook.last_delivery_status = "failed"

            logger.error(
                "webhook_delivery_failed_max_retries",
                webhook_id=webhook.id,
                delivery_id=delivery.id,
                attempts=delivery.attempts,
                error=delivery.error_message,
            )

    async def retry_pending_deliveries(self) -> int:
        """Retry all pending deliveries that are due for retry.

        Returns:
            Number of deliveries retried
        """
        query = select(WebhookDelivery).where(
            WebhookDelivery.status == "pending",
            WebhookDelivery.next_retry_at.isnot(None),
            WebhookDelivery.next_retry_at <= datetime.utcnow(),
        )

        result = await self.db.execute(query)
        deliveries = result.scalars().all()

        logger.info("retrying_webhook_deliveries", count=len(deliveries))

        retried = 0
        for delivery in deliveries:
            # Get webhook
            webhook_result = await self.db.execute(
                select(Webhook).where(Webhook.id == delivery.webhook_id)
            )
            webhook = webhook_result.scalar_one_or_none()

            if webhook and webhook.is_active:
                await self._attempt_delivery(webhook, delivery)
                retried += 1

        await self.db.commit()
        return retried

    @staticmethod
    def _generate_signature(payload: dict[str, Any], secret: str) -> str:
        """Generate HMAC signature for webhook payload.

        Args:
            payload: Webhook payload
            secret: Webhook secret

        Returns:
            HMAC signature
        """
        import json

        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode("utf-8"),
            payload_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"sha256={signature}"
