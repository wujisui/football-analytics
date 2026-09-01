"""默认联赛勾选必须覆盖当日 [荐]。

日推候选池按目录联赛选（所有 is_catalog 都拉盘口），而默认勾选原先只认热门。
两套范围不一致时，落在未勾热门目录联赛上的 [荐] 会被默认筛选整场藏掉：
09-01 实际推 4 场，其中德国杯不在热门，【比赛】列表只显示 3 场。
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.leagues import get_league_filter_options
from app.core.database import Base
from app.models.favorite_fixture import (
    FAVORITE_SOURCE_AUTO,
    FAVORITE_SOURCE_MANUAL,
    FavoriteFixture,
)
from app.models.fixture import Fixture
from app.models.league import League
from app.services.user_scope import ANON_OWNER_ID

HOT_LEAGUE = 39
CUP_LEAGUE = 81
QUIET_LEAGUE = 62
MATCH_DAY = "2026-09-01"


async def _seed() -> tuple[object, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    db = factory()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add_all(
        (
            League(
                id=HOT_LEAGUE,
                name="英超",
                country="England",
                season="2026",
                is_catalog=True,
                is_hot=True,
            ),
            League(
                id=CUP_LEAGUE,
                name="德国杯",
                country="Germany",
                season="2026",
                is_catalog=True,
                is_hot=False,
            ),
            League(
                id=QUIET_LEAGUE,
                name="法乙",
                country="France",
                season="2026",
                is_catalog=True,
                is_hot=False,
            ),
        )
    )
    for fixture_id, league_id in (
        (1, HOT_LEAGUE),
        (2, CUP_LEAGUE),
        (3, QUIET_LEAGUE),
    ):
        db.add(
            Fixture(
                id=fixture_id,
                league_id=league_id,
                home_team_id=1,
                away_team_id=2,
                date=now + timedelta(hours=6),
                match_day=MATCH_DAY,
                status="pending",
            )
        )
    await db.commit()
    return db, engine


def _option_by_league(payload: object) -> dict[int, object]:
    return {
        opt.league_id: opt
        for opt in [*payload.configured, *payload.extra]  # type: ignore[attr-defined]
    }


def test_auto_pick_league_is_checked_by_default_even_when_not_hot() -> None:
    async def _run() -> None:
        db, engine = await _seed()
        try:
            db.add(
                FavoriteFixture(
                    user_id=ANON_OWNER_ID,
                    fixture_id=2,
                    source=FAVORITE_SOURCE_AUTO,
                    auto_market="ah",
                    auto_lean="胜",
                    auto_handicap_lean="让胜(+8)",
                    saved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            await db.commit()

            payload = await get_league_filter_options(
                date_str=MATCH_DAY, days=1, scope="prematch", db=db
            )
            options = _option_by_league(payload)

            # 分组不变：未勾热门仍归「其他」，只是默认勾上。
            assert options[CUP_LEAGUE].tier == "extra"
            assert options[CUP_LEAGUE].default_checked is True
            assert options[HOT_LEAGUE].default_checked is True
            # 同样非热门但当日没有 [荐] 的联赛不受影响。
            assert options[QUIET_LEAGUE].default_checked is False
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())


def test_manual_favorite_does_not_force_a_league_default() -> None:
    """只有 [荐] 撑开默认勾选；手动关注是用户私有列表，不该改动全局筛选。"""

    async def _run() -> None:
        db, engine = await _seed()
        try:
            db.add(
                FavoriteFixture(
                    user_id="u-1",
                    fixture_id=2,
                    source=FAVORITE_SOURCE_MANUAL,
                    saved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            await db.commit()

            payload = await get_league_filter_options(
                date_str=MATCH_DAY, days=1, scope="prematch", db=db
            )
            assert _option_by_league(payload)[CUP_LEAGUE].default_checked is False
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())


def test_stale_ah_push_pick_does_not_force_a_league_default() -> None:
    """残留的独立「让平」在列表里是隐藏的，不该为它撑开一个联赛。"""

    async def _run() -> None:
        db, engine = await _seed()
        try:
            db.add(
                FavoriteFixture(
                    user_id=ANON_OWNER_ID,
                    fixture_id=2,
                    source=FAVORITE_SOURCE_AUTO,
                    auto_market="ah",
                    auto_handicap_lean="让平(0)",
                    saved_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            await db.commit()

            payload = await get_league_filter_options(
                date_str=MATCH_DAY, days=1, scope="prematch", db=db
            )
            assert _option_by_league(payload)[CUP_LEAGUE].default_checked is False
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())
