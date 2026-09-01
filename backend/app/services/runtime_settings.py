"""Runtime feature flags stored in ``app_settings`` (override env defaults)."""

from __future__ import annotations

import json
import logging
import time
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

KEY_ENABLE_FREE_QUOTA = "enable_free_quota"
KEY_SUBSCRIPTION_DENSE_ODDS = "subscription_dense_odds"
KEY_LAST_SYNC_RUN = "last_sync_run"
KEY_API_SPORTS_KEY = "api_sports_key"
KEY_CLIENT_DATA_REVISION = "client_data_revision"

SettingSource = Literal["db", "env"]

# Process cache for official keys stored in app_settings.
_runtime_api_sports_keys_blob: str | None = None
_runtime_api_sports_keys_loaded: bool = False
# Process cache for the admin「免费配额」switch (H2H / date clip read this sync).
_runtime_free_quota: bool | None = None


def get_runtime_api_sports_keys_blob() -> tuple[str | None, bool]:
    """Return the DB-backed key blob and whether it has been loaded."""
    return _runtime_api_sports_keys_blob, _runtime_api_sports_keys_loaded


def set_runtime_api_sports_keys_blob(blob: str | None) -> None:
    global _runtime_api_sports_keys_blob, _runtime_api_sports_keys_loaded
    _runtime_api_sports_keys_blob = blob
    _runtime_api_sports_keys_loaded = True


async def hydrate_api_sports_keys(
    session: AsyncSession | None = None,
) -> str | None:
    """Load the administrator-managed key list into process memory."""

    async def _read(db: AsyncSession) -> str | None:
        row = await get_setting_row(db, KEY_API_SPORTS_KEY)
        if row is None or not (row.value or "").strip():
            set_runtime_api_sports_keys_blob(None)
            return None
        value = row.value.strip()
        set_runtime_api_sports_keys_blob(value)
        return value

    if session is not None:
        return await _read(session)
    async with AsyncSessionLocal() as db:
        return await _read(db)


async def get_api_sports_keys_setting(
    session: AsyncSession | None = None,
) -> str | None:
    """Return the administrator-managed key list. Does not mask."""
    return await hydrate_api_sports_keys(session)


async def set_api_sports_keys_setting(
    session: AsyncSession,
    keys_blob: str,
) -> str | None:
    """Persist comma-separated keys. Empty input removes all official keys."""
    from app.services.api_key_pool import parse_api_sports_keys, reset_pool_state_for_key_change

    cleaned = ",".join(parse_api_sports_keys(keys_blob))
    row = await get_setting_row(session, KEY_API_SPORTS_KEY)
    if not cleaned:
        if row is not None:
            await session.delete(row)
            await session.commit()
        set_runtime_api_sports_keys_blob(None)
        await reset_pool_state_for_key_change(session)
        return None

    if row is None:
        session.add(AppSetting(key=KEY_API_SPORTS_KEY, value=cleaned))
    else:
        row.value = cleaned
    await session.commit()
    set_runtime_api_sports_keys_blob(cleaned)
    await reset_pool_state_for_key_change(session)
    return cleaned


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    text = raw.strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


async def get_setting_row(session: AsyncSession, key: str) -> AppSetting | None:
    result = await session.execute(select(AppSetting).where(AppSetting.key == key))
    return result.scalar_one_or_none()


async def _get_bool_setting(
    key: str,
    env_default: bool,
    session: AsyncSession | None = None,
) -> tuple[bool, SettingSource]:
    async def _read(db: AsyncSession) -> tuple[bool, SettingSource]:
        row = await get_setting_row(db, key)
        if row is None:
            return env_default, "env"
        parsed = _parse_bool(row.value)
        if parsed is None:
            return env_default, "env"
        return parsed, "db"

    if session is not None:
        return await _read(session)
    async with AsyncSessionLocal() as db:
        return await _read(db)


async def _set_bool_setting(session: AsyncSession, key: str, enabled: bool) -> bool:
    row = await get_setting_row(session, key)
    value = "true" if enabled else "false"
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    await session.commit()
    return enabled


def cached_enable_free_quota() -> bool:
    """Sync view of the free-quota flag; env default until hydrated."""
    if _runtime_free_quota is not None:
        return _runtime_free_quota
    return bool(get_settings().ENABLE_FREE_QUOTA)


def set_cached_enable_free_quota(enabled: bool) -> None:
    global _runtime_free_quota
    _runtime_free_quota = bool(enabled)


async def get_enable_free_quota(
    session: AsyncSession | None = None,
) -> tuple[bool, SettingSource]:
    """Effective flag: DB row if present, else env ``ENABLE_FREE_QUOTA`` (default ON)."""
    enabled, source = await _get_bool_setting(
        KEY_ENABLE_FREE_QUOTA,
        bool(get_settings().ENABLE_FREE_QUOTA),
        session,
    )
    set_cached_enable_free_quota(enabled)
    return enabled, source


async def set_enable_free_quota(session: AsyncSession, enabled: bool) -> bool:
    value = await _set_bool_setting(session, KEY_ENABLE_FREE_QUOTA, enabled)
    set_cached_enable_free_quota(value)
    return value


async def get_subscription_enabled(
    session: AsyncSession | None = None,
) -> tuple[bool, SettingSource]:
    """Subscription is the product-facing inverse of the legacy free-quota flag."""
    free_quota, source = await get_enable_free_quota(session)
    return not free_quota, source


async def set_subscription_enabled(
    session: AsyncSession,
    subscribed: bool,
) -> bool:
    await set_enable_free_quota(session, not subscribed)
    await set_subscription_dense_odds(session, subscribed)
    return bool(subscribed)


async def get_subscription_dense_odds(
    session: AsyncSession | None = None,
) -> tuple[bool, SettingSource]:
    """Whether a subscriber uses the continuous 30-minute odds schedule."""
    return await _get_bool_setting(KEY_SUBSCRIPTION_DENSE_ODDS, True, session)


async def set_subscription_dense_odds(
    session: AsyncSession,
    enabled: bool,
) -> bool:
    return await _set_bool_setting(session, KEY_SUBSCRIPTION_DENSE_ODDS, enabled)


async def get_last_sync_run(
    session: AsyncSession | None = None,
) -> dict | None:
    """Last finished official sync batch: time, mode, status, quota spent."""

    async def _read(db: AsyncSession) -> dict | None:
        row = await get_setting_row(db, KEY_LAST_SYNC_RUN)
        raw = (row.value if row else "").strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid %s JSON; ignoring", KEY_LAST_SYNC_RUN)
            return None
        return payload if isinstance(payload, dict) else None

    if session is not None:
        return await _read(session)
    async with AsyncSessionLocal() as db:
        return await _read(db)


async def set_last_sync_run(session: AsyncSession, run: dict) -> dict:
    payload = json.dumps(run, separators=(",", ":"), ensure_ascii=False)
    row = await get_setting_row(session, KEY_LAST_SYNC_RUN)
    if row is None:
        session.add(AppSetting(key=KEY_LAST_SYNC_RUN, value=payload))
    else:
        row.value = payload
    await session.commit()
    return run


async def get_client_data_revision(
    session: AsyncSession | None = None,
) -> str:
    """Persistent token changed after list/recommendation data is rewritten."""

    async def _read(db: AsyncSession) -> str:
        row = await get_setting_row(db, KEY_CLIENT_DATA_REVISION)
        return (row.value if row else "0").strip() or "0"

    if session is not None:
        return await _read(session)
    async with AsyncSessionLocal() as db:
        return await _read(db)


async def touch_client_data_revision(session: AsyncSession) -> str:
    """Publish one completed local-data mutation to connected clients."""
    revision = str(time.time_ns())
    row = await get_setting_row(session, KEY_CLIENT_DATA_REVISION)
    if row is None:
        session.add(AppSetting(key=KEY_CLIENT_DATA_REVISION, value=revision))
    else:
        row.value = revision
    await session.commit()
    return revision


async def get_hot_league_ids(
    session: AsyncSession | None = None,
) -> tuple[list[int], SettingSource]:
    """Catalog leagues highlighted by the administrator as hot."""
    from app.services.league_catalog import hot_league_ids

    async def _read(db: AsyncSession) -> tuple[list[int], SettingSource]:
        return await hot_league_ids(db), "db"

    if session is not None:
        return await _read(session)
    async with AsyncSessionLocal() as db:
        return await _read(db)


async def get_catalog_league_ids(
    session: AsyncSession | None = None,
) -> tuple[list[int], SettingSource]:
    """All leagues visible on the Hot Leagues administration page."""
    from app.services.league_catalog import catalog_league_ids

    async def _read(db: AsyncSession) -> tuple[list[int], SettingSource]:
        return await catalog_league_ids(db), "db"

    if session is not None:
        return await _read(session)
    async with AsyncSessionLocal() as db:
        return await _read(db)


async def set_hot_league_ids(
    session: AsyncSession,
    league_ids: list[int],
) -> list[int]:
    from app.services.league_catalog import set_hot_league_ids as save_hot_ids

    return await save_hot_ids(session, league_ids)
