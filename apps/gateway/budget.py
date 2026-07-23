"""
Per-tenant token budgets, enforced per minute and per day. Exhausted
budgets return 429 with a retry-after, which is enforcement rather than
observation: an over-quota tenant is throttled automatically.
"""
import os
import time

# "tenant:per_minute:per_day,..."
_DEFAULT = "dev:20000:400000,mobile:20000:400000"


def limits() -> dict[str, tuple[int, int]]:
    out = {}
    for part in os.getenv("TENANT_TOKEN_LIMITS", _DEFAULT).split(","):
        tenant, per_min, per_day = part.strip().split(":")
        out[tenant] = (int(per_min), int(per_day))
    return out


def check(r, tenant: str) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds)."""
    per_min, per_day = limits().get(tenant, (20000, 400000))
    now = int(time.time())
    minute_used = int(r.get(f"quota:{tenant}:m:{now // 60}") or 0)
    day_used = int(r.get(f"quota:{tenant}:d:{now // 86400}") or 0)
    if minute_used >= per_min:
        return False, 60 - now % 60
    if day_used >= per_day:
        return False, 86400 - now % 86400
    return True, 0


def consume(r, tenant: str, tokens: int):
    now = int(time.time())
    minute_key = f"quota:{tenant}:m:{now // 60}"
    day_key = f"quota:{tenant}:d:{now // 86400}"
    pipe = r.pipeline()
    pipe.incrby(minute_key, tokens)
    pipe.expire(minute_key, 120)
    pipe.incrby(day_key, tokens)
    pipe.expire(day_key, 90000)
    pipe.execute()
