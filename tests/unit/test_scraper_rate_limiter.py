"""Tests for rate limiter."""

import asyncio
import time

import pytest

from src.scraper.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_basic() -> None:
    """Test basic rate limiting."""
    limiter = RateLimiter(rate_limit=0.1, burst_size=1)

    start = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    # Should take at least 0.1 seconds for second request
    assert elapsed >= 0.1


@pytest.mark.asyncio
async def test_rate_limiter_burst() -> None:
    """Test burst capacity."""
    limiter = RateLimiter(rate_limit=0.1, burst_size=3)

    start = time.monotonic()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    # First 3 requests should be immediate (burst)
    assert elapsed < 0.05


@pytest.mark.asyncio
async def test_rate_limiter_refill() -> None:
    """Test token refill over time."""
    limiter = RateLimiter(rate_limit=0.1, burst_size=1)

    # Use one token
    await limiter.acquire()

    # Wait for refill
    await asyncio.sleep(0.15)

    # Should be able to acquire immediately
    start = time.monotonic()
    await limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed < 0.05


def test_rate_limiter_sync() -> None:
    """Test synchronous rate limiting."""
    limiter = RateLimiter(rate_limit=0.1, burst_size=1)

    start = time.monotonic()
    limiter.acquire_sync()
    limiter.acquire_sync()
    elapsed = time.monotonic() - start

    # Should take at least 0.1 seconds for second request
    assert elapsed >= 0.1


@pytest.mark.asyncio
async def test_rate_limiter_concurrent() -> None:
    """Test concurrent access to rate limiter."""
    limiter = RateLimiter(rate_limit=0.1, burst_size=1)

    async def make_request() -> float:
        await limiter.acquire()
        return time.monotonic()

    start = time.monotonic()
    times = await asyncio.gather(*[make_request() for _ in range(3)])
    elapsed = time.monotonic() - start

    # Should take at least 0.2 seconds for 3 requests (0.1s between each)
    assert elapsed >= 0.2

    # Check that times are properly spaced
    for i in range(len(times) - 1):
        assert times[i + 1] - times[i] >= 0.09  # Allow small margin
