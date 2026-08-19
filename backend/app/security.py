from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


@dataclass
class TokenBucket:
    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: int = 1) -> float:
        if self.tokens >= tokens:
            return 0.0
        deficit = tokens - self.tokens
        return deficit / self.refill_rate


class RateLimiterStore:
    """Per-IP token bucket store with LRU eviction."""

    def __init__(
        self, capacity: float, refill_rate: float, max_buckets: int = 10_000
    ) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.max_buckets = max_buckets
        self._buckets: dict[str, TokenBucket] = {}

    def is_allowed(self, client_ip: str) -> tuple[bool, float]:
        if client_ip not in self._buckets:
            if len(self._buckets) >= self.max_buckets:
                self._evict_oldest()
            self._buckets[client_ip] = TokenBucket(
                capacity=self.capacity, refill_rate=self.refill_rate
            )
        bucket = self._buckets[client_ip]
        allowed = bucket.consume()
        retry_after = 0.0 if allowed else bucket.time_until_available()
        return allowed, retry_after

    def _evict_oldest(self) -> None:
        oldest_ip = min(self._buckets, key=lambda ip: self._buckets[ip].last_refill)
        del self._buckets[oldest_ip]


EXPENSIVE_PATHS: set[str] = {"/generate", "/investigate"}
HEALTH_PATHS: set[str] = {"/health"}


def classify_endpoint(path: str) -> str:
    """Classify an endpoint for rate limit tier selection."""
    if path in HEALTH_PATHS:
        return "health"
    if path in EXPENSIVE_PATHS:
        return "expensive"
    return "default"


def get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For behind a reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "X-DNS-Prefetch-Control": "off",
    "Cache-Control": "no-store",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,  # noqa: ANN001
        *,
        health_rpm: int = 60,
        expensive_rpm: int = 5,
        default_rpm: int = 20,
    ) -> None:
        super().__init__(app)
        # Each tier gets its own store: capacity = rpm, refill_rate = rpm/60 tokens per second
        self._stores: dict[str, RateLimiterStore] = {
            "health": RateLimiterStore(
                capacity=health_rpm, refill_rate=health_rpm / 60.0
            ),
            "expensive": RateLimiterStore(
                capacity=expensive_rpm, refill_rate=expensive_rpm / 60.0
            ),
            "default": RateLimiterStore(
                capacity=default_rpm, refill_rate=default_rpm / 60.0
            ),
        }

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        tier = classify_endpoint(request.url.path)
        client_ip = get_client_ip(request)
        store = self._stores[tier]
        allowed, retry_after = store.is_allowed(client_ip)

        if not allowed:
            retry_seconds = math.ceil(retry_after)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(retry_seconds)},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        response = await call_next(request)
        for header_name, header_value in SECURITY_HEADERS.items():
            response.headers[header_name] = header_value
        # Remove Server header to prevent technology disclosure
        if "server" in response.headers:
            del response.headers["server"]
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_body_bytes: int = 55 * 1024 * 1024) -> None:  # noqa: ANN001
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except (ValueError, TypeError):
                length = 0
            if length > self.max_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )
        return await call_next(request)
