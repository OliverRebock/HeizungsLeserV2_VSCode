from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from threading import Lock

from app.core.config import settings


@dataclass
class AttemptBucket:
    attempts: deque[datetime] = field(default_factory=deque)
    locked_until: datetime | None = None


class LoginRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[str, AttemptBucket] = {}

    def check_allowed(self, *keys: str) -> int | None:
        now = datetime.now(UTC)
        with self._lock:
            retry_after: int | None = None
            for key in keys:
                bucket = self._buckets.get(key)
                if not bucket:
                    continue
                self._prune_bucket(bucket, now)
                if bucket.locked_until and bucket.locked_until > now:
                    seconds_remaining = int((bucket.locked_until - now).total_seconds())
                    retry_after = max(retry_after or 0, seconds_remaining)
            return retry_after

    def register_failure(self, *keys: str) -> int | None:
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
        lockout_seconds: int | None = None
        with self._lock:
            for key in keys:
                bucket = self._buckets.setdefault(key, AttemptBucket())
                while bucket.attempts and bucket.attempts[0] < window_start:
                    bucket.attempts.popleft()
                bucket.attempts.append(now)
                if len(bucket.attempts) >= settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
                    bucket.locked_until = now + timedelta(seconds=settings.LOGIN_LOCKOUT_SECONDS)
                    lockout_seconds = max(lockout_seconds or 0, settings.LOGIN_LOCKOUT_SECONDS)
            return lockout_seconds

    def register_success(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._buckets.pop(key, None)

    def _prune_bucket(self, bucket: AttemptBucket, now: datetime) -> None:
        window_start = now - timedelta(seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
        while bucket.attempts and bucket.attempts[0] < window_start:
            bucket.attempts.popleft()
        if bucket.locked_until and bucket.locked_until <= now:
            bucket.locked_until = None
        if not bucket.attempts and not bucket.locked_until:
            empty_keys = [key for key, current in self._buckets.items() if current is bucket]
            for key in empty_keys:
                self._buckets.pop(key, None)


login_rate_limiter = LoginRateLimiter()