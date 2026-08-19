"""Official API-Sports key pool with same-day failover after quota exhaustion.

Source: admin-saved comma-separated keys in ``app_settings``
(``api_sports_key``), configured via Mine admin UI or ``manage.py set-api-sports-key``.

When the active key hits the daily request limit, the fetcher marks it
exhausted for the scheduler-local calendar day and switches to the next key
without restarting the process.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

KEY_API_SPORTS_POOL_STATE = "api_sports_key_pool_state"
_SPLIT_RE = re.compile(r"[,;\s]+")

# Process-local view (hydrated from DB at fetcher enter / after rotate).
_day: str | None = None
_active_index: int = 0
_exhausted: set[int] = set()
_hydrated: bool = False


@dataclass(frozen=True)
class KeyPoolStatus:
    day: str
    key_count: int
    active_index: int
    exhausted_indexes: list[int]
    active_suffix: str


def parse_api_sports_keys(*parts: str) -> list[str]:
    """Parse and deduplicate one or more administrator-provided key fragments."""
    seen: set[str] = set()
    out: list[str] = []
    placeholders = {
        "",
        "your_api_key_here",
        "your-api-key-here",
        "your_api_sports_key_here",
    }
    for part in parts:
        for token in _SPLIT_RE.split(part or ""):
            key = token.strip()
            if not key or key in placeholders or key in seen:
                continue
            seen.add(key)
            out.append(key)
    return out


def official_keys(settings: Settings | None = None) -> list[str]:
    from app.services.runtime_settings import get_runtime_api_sports_keys_blob

    blob, _loaded = get_runtime_api_sports_keys_blob()
    return parse_api_sports_keys(blob or "")


def mask_api_sports_keys_blob(raw: str | None) -> str:
    """UI-safe preview: only last 4 chars of each key."""
    keys = parse_api_sports_keys(raw or "")
    return ",".join(f"…{_key_suffix(k)}" for k in keys)


async def reset_pool_state_for_key_change(
    session: AsyncSession | None = None,
    settings: Settings | None = None,
) -> None:
    """After admin replaces the key list, restart failover from key #1 today."""
    global _day, _active_index, _exhausted, _hydrated
    settings = settings or get_settings()
    day = _scheduler_day(settings)
    _day = day
    _active_index = 0
    _exhausted = set()
    _hydrated = True
    await _persist_state(session, day)


def _scheduler_day(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date().isoformat()


def _key_suffix(key: str) -> str:
    text = key.strip()
    if len(text) <= 4:
        return text
    return text[-4:]


def _reset_memory_for_day(day: str) -> None:
    global _day, _active_index, _exhausted, _hydrated
    _day = day
    _active_index = 0
    _exhausted = set()
    _hydrated = True


def _apply_state(day: str, active_index: int, exhausted: set[int], key_count: int) -> None:
    global _day, _active_index, _exhausted, _hydrated
    _day = day
    if key_count <= 0:
        _active_index = 0
        _exhausted = set()
    else:
        _exhausted = {i for i in exhausted if 0 <= i < key_count}
        if active_index not in _exhausted and 0 <= active_index < key_count:
            _active_index = active_index
        else:
            _active_index = next(
                (i for i in range(key_count) if i not in _exhausted),
                0,
            )
    _hydrated = True


def memory_active_index() -> int:
    return _active_index


def memory_exhausted_indexes() -> list[int]:
    return sorted(_exhausted)


def active_official_key(settings: Settings | None = None) -> str | None:
    """Return the current official key, or None when all are exhausted / missing."""
    settings = settings or get_settings()
    keys = official_keys(settings)
    if not keys:
        return None
    day = _scheduler_day(settings)
    if _day != day:
        # New day before hydrate: start from key 0 until DB hydrate runs.
        _reset_memory_for_day(day)
    if _active_index in _exhausted or not (0 <= _active_index < len(keys)):
        nxt = next((i for i in range(len(keys)) if i not in _exhausted), None)
        if nxt is None:
            return None
        return keys[nxt]
    return keys[_active_index]


def pool_status(settings: Settings | None = None) -> KeyPoolStatus:
    settings = settings or get_settings()
    keys = official_keys(settings)
    day = _day or _scheduler_day(settings)
    active = active_official_key(settings)
    return KeyPoolStatus(
        day=day,
        key_count=len(keys),
        active_index=_active_index if keys else 0,
        exhausted_indexes=sorted(_exhausted),
        active_suffix=_key_suffix(active) if active else "",
    )


def _state_payload(day: str, active_index: int, exhausted: set[int]) -> str:
    return json.dumps(
        {
            "day": day,
            "active_index": active_index,
            "exhausted_indexes": sorted(exhausted),
        },
        ensure_ascii=False,
    )


async def hydrate_key_pool(
    session: AsyncSession | None = None,
    settings: Settings | None = None,
) -> KeyPoolStatus:
    """Load today's exhausted/active indexes from ``app_settings`` into memory."""
    from app.core.database import AsyncSessionLocal
    from app.services.runtime_settings import get_setting_row

    settings = settings or get_settings()
    keys = official_keys(settings)
    day = _scheduler_day(settings)
    key_count = len(keys)

    async def _read(db: AsyncSession) -> None:
        row = await get_setting_row(db, KEY_API_SPORTS_POOL_STATE)
        if row is None or not row.value:
            _reset_memory_for_day(day)
            return
        try:
            data = json.loads(row.value)
        except json.JSONDecodeError:
            _reset_memory_for_day(day)
            return
        stored_day = str(data.get("day") or "")
        if stored_day != day:
            _reset_memory_for_day(day)
            return
        exhausted = {
            int(x)
            for x in (data.get("exhausted_indexes") or [])
            if str(x).isdigit() or isinstance(x, int)
        }
        active = int(data.get("active_index") or 0)
        _apply_state(day, active, exhausted, key_count)

    if session is not None:
        await _read(session)
    else:
        async with AsyncSessionLocal() as db:
            await _read(db)
    return pool_status(settings)


async def _persist_state(session: AsyncSession | None, day: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.models.app_setting import AppSetting
    from app.services.runtime_settings import get_setting_row

    payload = _state_payload(day, _active_index, _exhausted)

    async def _write(db: AsyncSession) -> None:
        row = await get_setting_row(db, KEY_API_SPORTS_POOL_STATE)
        if row is None:
            db.add(AppSetting(key=KEY_API_SPORTS_POOL_STATE, value=payload))
        else:
            row.value = payload
        await db.commit()

    if session is not None:
        await _write(session)
    else:
        async with AsyncSessionLocal() as db:
            await _write(db)


async def mark_active_exhausted_and_rotate(
    session: AsyncSession | None = None,
    settings: Settings | None = None,
    *,
    reason: str = "quota",
) -> str | None:
    """Mark the current official key exhausted for today; return the next key.

    Returns ``None`` when no backup key remains for today.
    """
    global _active_index

    settings = settings or get_settings()
    keys = official_keys(settings)
    if not keys:
        return None

    await hydrate_key_pool(session, settings)
    day = _scheduler_day(settings)
    current = _active_index if 0 <= _active_index < len(keys) else 0
    _exhausted.add(current)
    nxt = next((i for i in range(len(keys)) if i not in _exhausted), None)
    if nxt is None:
        _active_index = current
        await _persist_state(session, day)
        logger.error(
            "All %s API-Sports keys exhausted for %s (%s); no failover left",
            len(keys),
            day,
            reason,
        )
        return None

    prev_suffix = _key_suffix(keys[current])
    _active_index = nxt
    await _persist_state(session, day)
    logger.warning(
        "API-Sports key failover (%s): …%s exhausted → key #%s/…%s (day=%s)",
        reason,
        prev_suffix,
        nxt + 1,
        _key_suffix(keys[nxt]),
        day,
    )
    return keys[nxt]


def describe_pool_for_logs(settings: Settings | None = None) -> dict[str, Any]:
    status = pool_status(settings)
    return {
        "day": status.day,
        "key_count": status.key_count,
        "active_index": status.active_index,
        "exhausted_indexes": status.exhausted_indexes,
        "active_suffix": status.active_suffix,
    }
