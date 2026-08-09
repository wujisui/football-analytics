"""Runtime feature flags stored in ``app_settings`` (override env defaults)."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.app_setting import AppSetting

KEY_ENABLE_SCHEDULED_FULL_DETAIL = "enable_scheduled_full_detail"

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


async def get_enable_scheduled_full_detail(
    session: AsyncSession | None = None,
) -> tuple[bool, SettingSource]:
    """Effective flag: DB row if present, else env ``ENABLE_SCHEDULED_FULL_DETAIL``."""
    env_default = bool(get_settings().ENABLE_SCHEDULED_FULL_DETAIL)

    async def _read(db: AsyncSession) -> tuple[bool, SettingSource]:
        row = await get_setting_row(db, KEY_ENABLE_SCHEDULED_FULL_DETAIL)
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


async def set_enable_scheduled_full_detail(
    session: AsyncSession,
    enabled: bool,
) -> bool:
    row = await get_setting_row(session, KEY_ENABLE_SCHEDULED_FULL_DETAIL)
    value = "true" if enabled else "false"
    if row is None:
        session.add(AppSetting(key=KEY_ENABLE_SCHEDULED_FULL_DETAIL, value=value))
    else:
        row.value = value
    await session.commit()
    return enabled
