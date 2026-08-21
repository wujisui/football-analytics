"""Runtime feature flags stored in ``app_settings`` (override env defaults)."""

from __future__ import annotations

import json
import logging
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

KEY_ENABLE_SCHEDULED_FULL_DETAIL = "enable_scheduled_full_detail"
KEY_ENABLE_FREE_QUOTA = "enable_free_quota"
KEY_API_SPORTS_KEY = "api_sports_key"
KEY_HOT_LEAGUE_IDS = "hot_league_ids"

# First-run 热门：五大联赛 + 欧冠/欧罗巴/欧协联 + 中超/日职联/韩K联。
# Catalog membership is still ``config/leagues.json``; this is the odds-sync subset.
DEFAULT_HOT_LEAGUE_IDS: tuple[int, ...] = (
    39,
    140,
    78,
    135,
    61,
    2,
    3,
    848,
    169,
    98,
    292,
)

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


def catalog_league_ids(settings=None) -> set[int]:
    cfg = settings or get_settings()
    return {int(value) for value in cfg.LEAGUE_IDS.values()}


def default_hot_league_ids(catalog: set[int] | None = None) -> list[int]:
    allowed = catalog if catalog is not None else catalog_league_ids()
    return [league_id for league_id in DEFAULT_HOT_LEAGUE_IDS if league_id in allowed]


def normalize_hot_league_ids(
    raw: list[int] | tuple[int, ...] | None,
    *,
    catalog: set[int] | None = None,
) -> list[int]:
    """Keep catalog order; drop unknown / duplicate ids."""
    allowed = catalog if catalog is not None else catalog_league_ids()
    wanted = {int(value) for value in (raw or [])}
    ordered: list[int] = []
    seen: set[int] = set()
    settings = get_settings()
    for league_id in settings.LEAGUE_IDS.values():
        lid = int(league_id)
        if lid in wanted and lid in allowed and lid not in seen:
            seen.add(lid)
            ordered.append(lid)
    return ordered


def _parse_hot_league_ids(raw: str | None, catalog: set[int]) -> list[int] | None:
    if raw is None or not str(raw).strip():
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid %s JSON; using default hot leagues", KEY_HOT_LEAGUE_IDS)
        return None
    if not isinstance(payload, list):
        return None
    ids: list[int] = []
    for item in payload:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return normalize_hot_league_ids(ids, catalog=catalog)


async def get_hot_league_ids(
    session: AsyncSession | None = None,
) -> tuple[list[int], SettingSource]:
    """Leagues that scheduled batches refresh pre-match odds for."""
    catalog = catalog_league_ids()

    async def _read(db: AsyncSession) -> tuple[list[int], SettingSource]:
        row = await get_setting_row(db, KEY_HOT_LEAGUE_IDS)
        parsed = _parse_hot_league_ids(row.value if row else None, catalog)
        if parsed is None:
            return default_hot_league_ids(catalog), "env"
        return parsed, "db"

    if session is not None:
        return await _read(session)
    async with AsyncSessionLocal() as db:
        return await _read(db)


async def set_hot_league_ids(
    session: AsyncSession,
    league_ids: list[int],
) -> list[int]:
    catalog = catalog_league_ids()
    selected = normalize_hot_league_ids(league_ids, catalog=catalog)
    payload = json.dumps(selected, separators=(",", ":"))
    row = await get_setting_row(session, KEY_HOT_LEAGUE_IDS)
    if row is None:
        session.add(AppSetting(key=KEY_HOT_LEAGUE_IDS, value=payload))
    else:
        row.value = payload
    await session.commit()
    return selected
