"""Webhook notification system."""

from src.webhooks.dispatcher import WebhookDispatcher
from src.webhooks.models import WebhookEvent

__all__ = ["WebhookDispatcher", "WebhookEvent"]
