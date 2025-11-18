"""Pydantic schemas for webhooks."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl

from src.storage.database.webhook_models import WebhookEvent


class WebhookCreate(BaseModel):
    """Webhook creation request."""

    name: str
    url: HttpUrl
    secret: Optional[str] = None
    events: list[WebhookEvent]
    headers: Optional[dict[str, str]] = None
    max_retries: int = 3
    retry_delay: int = 60


class WebhookUpdate(BaseModel):
    """Webhook update request."""

    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    secret: Optional[str] = None
    events: Optional[list[WebhookEvent]] = None
    headers: Optional[dict[str, str]] = None
    is_active: Optional[bool] = None
    max_retries: Optional[int] = None
    retry_delay: Optional[int] = None


class WebhookResponse(BaseModel):
    """Webhook response."""

    id: int
    user_id: int
    name: str
    url: str
    is_active: bool
    events: list[str]
    headers: Optional[dict[str, str]]
    max_retries: int
    retry_delay: int
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_delivery_at: Optional[datetime]
    last_delivery_status: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery response."""

    id: int
    webhook_id: int
    event: str
    payload: dict
    status: str
    attempts: int
    response_code: Optional[int]
    response_body: Optional[str]
    error_message: Optional[str]
    delivered_at: Optional[datetime]
    next_retry_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookTestPayload(BaseModel):
    """Webhook test payload."""

    message: str = "Test webhook delivery"
    data: Optional[dict] = None
