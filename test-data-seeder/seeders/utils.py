"""Shared seeder helpers: time distribution, ID generation, batch insert."""
import random
import string
import uuid
from datetime import datetime, timedelta, timezone


_used_invite_codes: set = set()


def random_invite_code() -> str:
    """A 6-char invite code guaranteed unique within this process.

    `hives.invite_code` carries a UNIQUE constraint, and the orchestrator seeds the global
    RNG with a FIXED value for reproducibility (orchestrator.py) — so two bare
    `random.choices(k=6)` call sites (the main hives seeder + the CMMS client-hive seeder)
    collide DETERMINISTICALLY under that seed, aborting `/api/seed/all` with a
    hives_invite_code_key violation. A UNIQUE key must never depend on RNG luck: regenerate
    until the code is unused (falling back to a uuid-derived code in the impossible case)."""
    for _ in range(1000):
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in _used_invite_codes:
            _used_invite_codes.add(code)
            return code
    code = uuid.uuid4().hex[:6].upper()
    _used_invite_codes.add(code)
    return code


def text_id(prefix: str = "seed") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def random_timestamp_in_last_n_days(n: int = 90, rng: random.Random | None = None) -> datetime:
    """Generates a timestamp distributed across the last `n` days with shift patterns.

    - 65% day shift (06:00-18:00)
    - 25% afternoon (18:00-00:00)
    - 10% night (00:00-06:00)
    - Weekdays weighted ~3x vs weekends.
    """
    r = rng or random
    now = datetime.now(timezone.utc)

    # Pick a day, weighted toward weekdays
    days_ago_pool = []
    for d in range(n):
        candidate = now - timedelta(days=d)
        weight = 3 if candidate.weekday() < 5 else 1
        days_ago_pool.extend([d] * weight)
    days_ago = r.choice(days_ago_pool)

    # Pick a shift
    shift_roll = r.random()
    if shift_roll < 0.65:
        hour = r.randint(6, 17)
    elif shift_roll < 0.90:
        hour = r.randint(18, 23)
    else:
        hour = r.randint(0, 5)
    minute = r.randint(0, 59)
    second = r.randint(0, 59)

    target = (now - timedelta(days=days_ago)).replace(
        hour=hour, minute=minute, second=second, microsecond=0
    )
    return target


def to_iso(dt: datetime) -> str:
    """ISO 8601 UTC string Supabase accepts."""
    return dt.astimezone(timezone.utc).isoformat()


def batch_insert(client, table: str, rows: list, chunk: int = 500) -> int:
    """Insert rows in batches; returns total inserted count."""
    inserted = 0
    for i in range(0, len(rows), chunk):
        batch = rows[i : i + chunk]
        client.table(table).insert(batch).execute()
        inserted += len(batch)
    return inserted
