import asyncio
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

import json

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.fixture import Fixture
from app.models.league import League
from app.models.pre_match_data import PreMatchData
from app.models.team import Team
from app.services.data_cleanup import (
    prune_low_value_data,
    should_prune_fixture,
    slim_expired_packages,
)

NOW = datetime(2026, 7, 26, 12, 0, 0)


def _fixture(
    status: str = "finished",
    *,
    date: datetime | None = None,
    home_goals: int | None = 2,
    away_goals: int | None = 1,
):
    return SimpleNamespace(
        status=status,
        date=date or datetime(2026, 7, 25, 12, 0, 0),
        home_goals=home_goals,
        away_goals=away_goals,
    )


def _analyzed_stored(*, board: bool = False):
    """Complete frozen prediction; ``board`` decides whether it had any basis."""
    odds = (
        json.dumps(
            {
                "available": True,
                "match_winner": {"home": "2.10", "draw": "3.30", "away": "3.40"},
            }
        )
        if board
        else None
    )
    return SimpleNamespace(
        recommendation="胜",
        score_hint="比分:2-1",
        goal_lean="大（2.5）",
        both_score_lean="双进:是",
        handicap_lean="让球胜（-0.5）",
        home_win_prob=0.48,
        draw_prob=0.27,
        away_win_prob=0.25,
        odds_json=odds,
        odds_opening_json=None,
    )


class PruneJudgmentTests(unittest.TestCase):
    def test_flat_probs_alone_do_not_keep_finished_fixture(self) -> None:
        stored = SimpleNamespace(
            recommendation="待分析",
            score_hint="比分:待分析",
            goal_lean="大小：待分析",
            both_score_lean="双进:待分析",
            handicap_lean="让球：待分析",
            home_win_prob=1 / 3,
            draw_prob=1 / 3,
            away_win_prob=1 / 3,
            odds_json=None,
            odds_opening_json=None,
        )
        feature = SimpleNamespace(
            features_json='{"has_odds": 0}',
            home_win_prob=1 / 3,
            draw_prob=1 / 3,
            away_win_prob=1 / 3,
        )
        self.assertTrue(should_prune_fixture(_fixture(), stored, feature))

    def test_prediction_without_board_is_pruned(self) -> None:
        """有预测但没赛前盘口 = 无依据预测，物理删除，不进历史统计。"""
        self.assertTrue(
            should_prune_fixture(_fixture(), _analyzed_stored(), None)
        )

    def test_prediction_with_board_keeps_fixture(self) -> None:
        self.assertFalse(
            should_prune_fixture(
                _fixture(), _analyzed_stored(board=True), None
            )
        )

    def test_board_only_from_feature_keeps_fixture(self) -> None:
        """盘口凭证也可以来自冻结特征（has_odds=1）。"""
        feature = SimpleNamespace(features_json='{"has_odds": 1}')
        self.assertFalse(should_prune_fixture(_fixture(), None, feature))

    def test_upcoming_pending_never_pruned(self) -> None:
        """开赛前的赛程必须留着，盘口常常临近开赛才开。"""
        self.assertFalse(
            should_prune_fixture(
                _fixture(
                    status="pending",
                    date=NOW + timedelta(days=2),
                    home_goals=None,
                    away_goals=None,
                ),
                None,
                None,
                now=NOW,
            )
        )

    def test_stale_pending_without_score_pruned(self) -> None:
        """状态一直卡在 pending 说明比分从未回写，官方也不会再补。

        这类场次在【比赛】里被开赛时刻过滤掉，在【赛果】里又判不了命中，
        真实库里积到 500 多场（如 8/14 单日 344 场），必须按永不结算清掉。
        """
        stale = _fixture(
            status="pending",
            date=NOW - timedelta(days=5),
            home_goals=None,
            away_goals=None,
        )
        self.assertTrue(should_prune_fixture(stale, None, None, now=NOW))
        self.assertTrue(
            should_prune_fixture(stale, _analyzed_stored(board=True), None, now=NOW)
        )

    def test_stale_live_with_score_kept_for_grading(self) -> None:
        """比分已回写但状态没推进的场次仍可判定，交给赛果结算。"""
        self.assertFalse(
            should_prune_fixture(
                _fixture(status="live", date=NOW - timedelta(days=5)),
                _analyzed_stored(board=True),
                None,
                now=NOW,
            )
        )

    def test_cancelled_pruned_even_with_full_prematch(self) -> None:
        """No full-time score will ever arrive, so the prediction can't be graded."""
        self.assertTrue(
            should_prune_fixture(
                _fixture(status="cancelled", home_goals=None, away_goals=None),
                _analyzed_stored(board=True),
                None,
                now=NOW,
            )
        )

    def test_finished_without_score_pruned_even_with_full_prematch(self) -> None:
        self.assertTrue(
            should_prune_fixture(
                _fixture(home_goals=None, away_goals=None),
                _analyzed_stored(board=True),
                None,
                now=NOW,
            )
        )

    def test_stale_postponed_pruned_but_fresh_one_kept(self) -> None:
        """Fresh postponed rows still show as upcoming; stale ones are dead weight."""
        stored = _analyzed_stored(board=True)
        fresh = _fixture(
            status="postponed",
            date=NOW - timedelta(hours=2),
            home_goals=None,
            away_goals=None,
        )
        stale = _fixture(
            status="postponed",
            date=NOW - timedelta(days=3),
            home_goals=None,
            away_goals=None,
        )
        self.assertFalse(should_prune_fixture(fresh, stored, None, now=NOW))
        self.assertTrue(should_prune_fixture(stale, stored, None, now=NOW))
        # 刚延期且还没开盘也留着：盘口常常临近开赛才开。
        self.assertFalse(should_prune_fixture(fresh, None, None, now=NOW))


class PruneAtScaleTests(unittest.TestCase):
    """每场要清 6 个快照 key，一次性 ``IN`` 会超出 SQLite 的绑定参数上限。

    真实库 6885 场 × 6 = 41310 个 key（上限 32766），``clean_old_data`` 直接
    ``too many SQL variables`` 失败，一条都没删掉。场次数取到上限之上才复现。
    """

    def test_prunes_more_fixtures_than_sqlite_variable_limit(self) -> None:
        fixture_count = 6000

        async def run() -> tuple[int, int]:
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(League(id=1, name="L", country="World", season=2026))
                session.add(Team(id=1, name="Home"))
                session.add(Team(id=2, name="Away"))
                await session.flush()
                await session.execute(
                    insert(Fixture),
                    [
                        {
                            "id": 1000 + i,
                            "league_id": 1,
                            "home_team_id": 1,
                            "away_team_id": 2,
                            "date": datetime(2026, 8, 1, 12, 0, 0),
                            "status": "finished",
                            "home_goals": 1,
                            "away_goals": 0,
                        }
                        for i in range(fixture_count)
                    ],
                )
                await session.commit()
                report = await prune_low_value_data(session, apply=True)
                left = await session.scalar(select(func.count()).select_from(Fixture))
            await engine.dispose()
            return report.fixtures_deleted, int(left or 0)

        deleted, left = asyncio.run(run())
        # 无赛前盘口的完场场次全删，快照 key 分块删除不再撞变量上限。
        self.assertEqual(deleted, fixture_count)
        self.assertEqual(left, 0)


class SlimExpiredPackageTests(unittest.TestCase):
    def test_keeps_frozen_prediction_and_odds_but_clears_details(self) -> None:
        async def run() -> tuple[int, PreMatchData]:
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(League(id=1, name="L", country="World", season=2026))
                session.add(Team(id=1, name="Home"))
                session.add(Team(id=2, name="Away"))
                session.add(
                    Fixture(
                        id=1,
                        league_id=1,
                        home_team_id=1,
                        away_team_id=2,
                        date=NOW - timedelta(days=8),
                        status="finished",
                        home_goals=2,
                        away_goals=1,
                    )
                )
                session.add(
                    PreMatchData(
                        fixture_id=1,
                        home_win_prob=0.5,
                        draw_prob=0.3,
                        away_win_prob=0.2,
                        recommendation="胜",
                        score_hint="比分:2-1",
                        goal_lean="大(2.5)",
                        both_score_lean="双进:是",
                        handicap_lean="让胜（主让0.5）",
                        odds_json='{"available":true}',
                        lineups_json='{"available":true}',
                        injuries_json='{"available":true}',
                        h2h_json='{"played":3}',
                    )
                )
                await session.commit()

                slimmed = await slim_expired_packages(session, cutoff=NOW)
                stored = (
                    await session.execute(
                        select(PreMatchData).where(PreMatchData.fixture_id == 1)
                    )
                ).scalar_one()
            await engine.dispose()
            return slimmed, stored

        slimmed, stored = asyncio.run(run())
        self.assertEqual(slimmed, 1)
        self.assertIsNone(stored.lineups_json)
        self.assertIsNone(stored.injuries_json)
        self.assertIsNone(stored.h2h_json)
        self.assertEqual(stored.recommendation, "胜")
        self.assertIsNotNone(stored.odds_json)


if __name__ == "__main__":
    unittest.main()
