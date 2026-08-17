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

SettingSource = Literal["db", "env"]


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
