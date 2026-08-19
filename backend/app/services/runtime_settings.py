"""Runtime feature flags stored in ``app_settings`` (override env defaults)."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.app_setting import AppSetting

KEY_ENABLE_SCHEDULED_FULL_DETAIL = "enable_scheduled_full_detail"
KEY_ENABLE_FREE_QUOTA = "enable_free_quota"
KEY_API_SPORTS_KEY = "api_sports_key"

SettingSource = Literal["db", "env"]

# Process cache for official keys stored in app_settings.
_runtime_api_sports_keys_blob: str | None = None
_runtime_api_sports_keys_loaded: bool = False


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


async def get_enable_scheduled_full_detail(
    session: AsyncSession | None = None,
) -> tuple[bool, SettingSource]:
    """Effective flag: DB row if present, else env ``ENABLE_SCHEDULED_FULL_DETAIL``."""
    return await _get_bool_setting(
        KEY_ENABLE_SCHEDULED_FULL_DETAIL,
        bool(get_settings().ENABLE_SCHEDULED_FULL_DETAIL),
        session,
    )


async def set_enable_scheduled_full_detail(
    session: AsyncSession,
    enabled: bool,
) -> bool:
    return await _set_bool_setting(session, KEY_ENABLE_SCHEDULED_FULL_DETAIL, enabled)


async def get_enable_free_quota(
    session: AsyncSession | None = None,
) -> tuple[bool, SettingSource]:
    """Effective flag: DB row if present, else env ``ENABLE_FREE_QUOTA`` (default ON)."""
    return await _get_bool_setting(
        KEY_ENABLE_FREE_QUOTA,
        bool(get_settings().ENABLE_FREE_QUOTA),
        session,
    )


async def set_enable_free_quota(session: AsyncSession, enabled: bool) -> bool:
    return await _set_bool_setting(session, KEY_ENABLE_FREE_QUOTA, enabled)
