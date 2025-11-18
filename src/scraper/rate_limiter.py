"""Rate limiting for scraper requests."""

import asyncio
import time
from typing import Optional

from src.core.config import get_settings
from src.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter with token bucket algorithm."""

    def __init__(
        self,
        rate_limit: Optional[float] = None,
        burst_size: int = 1,
    ) -> None:
        """Initialize rate limiter.

        Args:
            rate_limit: Minimum seconds between requests (default from settings)
            burst_size: Maximum number of tokens (burst capacity)
        """
        self.rate_limit = rate_limit or settings.scraper_rate_limit
        self.burst_size = burst_size
        self.tokens = float(burst_size)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to make a request (async).

        Will wait until a token is available.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(
                self.burst_size,
                self.tokens + elapsed / self.rate_limit,
            )
            self.last_update = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * self.rate_limit
                logger.debug("rate_limit_wait", wait_time=wait_time)
                await asyncio.sleep(wait_time)
                self.tokens = 1
                self.last_update = time.monotonic()

            # Consume one token
            self.tokens -= 1
            logger.debug("rate_limit_acquired", remaining_tokens=self.tokens)

    def acquire_sync(self) -> None:
        """Acquire permission to make a request (sync).

        Will wait until a token is available.
        """
        now = time.monotonic()
        elapsed = now - self.last_update

        # Refill tokens based on elapsed time
        self.tokens = min(
            self.burst_size,
            self.tokens + elapsed / self.rate_limit,
        )
        self.last_update = now

        # Wait if no tokens available
        if self.tokens < 1:
            wait_time = (1 - self.tokens) * self.rate_limit
            logger.debug("rate_limit_wait_sync", wait_time=wait_time)
            time.sleep(wait_time)
            self.tokens = 1
            self.last_update = time.monotonic()

        # Consume one token
        self.tokens -= 1
        logger.debug("rate_limit_acquired_sync", remaining_tokens=self.tokens)


# Global rate limiter instance
_global_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter()
    return _global_limiter
