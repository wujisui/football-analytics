"""Database-backed league catalog and display categories."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.app_setting import AppSetting
from app.models.league import League, LeagueCategory, LeagueCatalogTombstone


CATEGORY_SEEDS: tuple[tuple[int, str], ...] = (
    (1, "五大联赛"),
    (2, "欧洲杯赛"),
    (3, "其他欧洲"),
    (4, "国际赛事"),
    (5, "洲际杯赛"),
    (6, "美洲"),
    (7, "亚洲及大洋洲"),
    (8, "各国杯赛"),
    (9, "其他"),
)

CATEGORY_BY_LEAGUE_ID: dict[int, int] = {
    39: 1,
    140: 1,
    78: 1,
    135: 1,
    61: 1,
    2: 2,
    3: 2,
    848: 2,
    40: 3,
    79: 3,
    62: 3,
    88: 3,
    89: 3,
    94: 3,
    179: 3,
    103: 3,
    113: 3,
    1: 4,
    4: 4,
    5: 4,
    9: 4,
    6: 4,
    7: 4,
    22: 4,
    10: 4,
    17: 5,
    13: 5,
    11: 5,
    16: 5,
    71: 6,
    128: 6,
    253: 6,
    169: 7,
    98: 7,
    292: 7,
    188: 7,
    307: 7,
}

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

# Official league 10 is the broad Friendlies feed, not a protected core
# competition. Keep it editable/deletable even when imported from the seed.
UNPROTECTED_SEED_LEAGUE_IDS: frozenset[int] = frozenset({10})


async def seed_league_catalog(session: AsyncSession) -> None:
    """Import the configured JSON catalog once; later changes live only in DB."""
    category_count = int(
        await session.scalar(select(func.count()).select_from(LeagueCategory)) or 0
    )
    if not category_count:
        for category_id, name in CATEGORY_SEEDS:
            session.add(
                LeagueCategory(id=category_id, name=name, sort_order=category_id * 10)
            )
        await session.flush()

    catalog_count = int(
        await session.scalar(
            select(func.count()).select_from(League).where(League.is_catalog.is_(True))
        )
        or 0
    )
    if catalog_count:
        await session.commit()
        return

    settings = get_settings()
    current_year = str(datetime.now().year)
    defaults = set(DEFAULT_HOT_LEAGUE_IDS)
    legacy_hot_row = await session.get(AppSetting, "hot_league_ids")
    if legacy_hot_row is not None:
        try:
            parsed = json.loads(legacy_hot_row.value)
            if isinstance(parsed, list):
                defaults = {int(value) for value in parsed}
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    for name, raw_id in settings.LEAGUE_IDS.items():
        league_id = int(raw_id)
        row = await session.get(League, league_id)
        country = settings.LEAGUE_COUNTRIES.get(league_id) or "Unknown"
        season = settings.configured_season(league_id) or current_year
        if row is None:
            row = League(
                id=league_id,
                name=name,
                country=country,
                season=season,
            )
            session.add(row)
        else:
            row.name = name
            row.country = country
            row.season = season
        row.category_id = CATEGORY_BY_LEAGUE_ID.get(league_id, 9)
        row.is_catalog = True
        row.is_hot = league_id in defaults
        row.is_protected = league_id not in UNPROTECTED_SEED_LEAGUE_IDS
    if legacy_hot_row is not None:
        await session.delete(legacy_hot_row)
    await session.commit()


async def catalog_leagues(session: AsyncSession) -> list[League]:
    rows = (
        await session.execute(
            select(League)
            .where(League.is_catalog.is_(True))
            .order_by(League.category_id, League.id)
        )
    ).scalars()
    return list(rows)


async def catalog_league_ids(session: AsyncSession) -> list[int]:
    rows = await session.execute(
        select(League.id)
        .where(League.is_catalog.is_(True))
        .order_by(League.category_id, League.id)
    )
    return [int(value) for value in rows.scalars()]


async def allowed_league_ids(session: AsyncSession) -> set[int]:
    from app.services.competition_scope import EXTRA_COMPETITION_IDS

    blocked = {
        int(value)
        for value in (
            await session.execute(select(LeagueCatalogTombstone.league_id))
        ).scalars()
    }
    return (
        set(await catalog_league_ids(session)) | set(EXTRA_COMPETITION_IDS)
    ) - blocked


async def hot_league_ids(session: AsyncSession) -> list[int]:
    rows = await session.execute(
        select(League.id)
        .where(League.is_catalog.is_(True), League.is_hot.is_(True))
        .order_by(League.category_id, League.id)
    )
    return [int(value) for value in rows.scalars()]


async def set_hot_league_ids(
    session: AsyncSession,
    league_ids: list[int],
) -> list[int]:
    wanted = {int(value) for value in league_ids}
    rows = await catalog_leagues(session)
    for row in rows:
        row.is_hot = int(row.id) in wanted
    await session.commit()
    return [int(row.id) for row in rows if row.is_hot]


async def retarget_catalog_league_id(
    session: AsyncSession,
    source: League,
    new_id: int,
) -> League:
    """Move an unprotected catalog league to another official ID.

    History under the old ID is discarded (it was fetched for the wrong
    competition). An existing non-catalog row at the new ID is promoted and
    keeps its fixtures. The mistyped ID is tombstoned so the date feed cannot
    put it back into the catalog.
    """
    next_id = int(new_id)
    if next_id < 1:
        raise ValueError("官方联赛 ID 必须为正整数")
    if source.is_protected:
        raise PermissionError("系统保护联赛不可修改官方 ID")
    old_id = int(source.id)
    if next_id == old_id:
        return source

    existing = await session.get(League, next_id)
    if existing is not None and existing.is_catalog:
        raise LookupError("该官方联赛 ID 已在目录中")
    if (
        existing is not None
        and existing.country
        and existing.country != "Unknown"
        and existing.country.casefold() != (source.country or "").casefold()
    ):
        raise ValueError(f"国家与本地官方记录不一致，应为 {existing.country}")

    country = source.country
    if existing is not None and existing.country and existing.country != "Unknown":
        country = existing.country
    attrs = {
        "name": source.name,
        "country": country,
        "season": source.season,
        "category_id": source.category_id,
        "is_catalog": True,
        "is_hot": source.is_hot,
        "is_protected": False,
    }
    await session.execute(delete(League).where(League.id == old_id))
    session.expunge(source)
    await session.flush()
    if existing is None:
        existing = League(id=next_id, **attrs)
        session.add(existing)
    else:
        for key, value in attrs.items():
            setattr(existing, key, value)
    if await session.get(LeagueCatalogTombstone, old_id) is None:
        session.add(LeagueCatalogTombstone(league_id=old_id))
    new_tombstone = await session.get(LeagueCatalogTombstone, next_id)
    if new_tombstone is not None:
        await session.delete(new_tombstone)
    await session.flush()
    return existing


async def league_categories(session: AsyncSession) -> list[LeagueCategory]:
    rows = (
        await session.execute(
            select(LeagueCategory).order_by(
                LeagueCategory.sort_order, LeagueCategory.id
            )
        )
    ).scalars()
    return list(rows)
