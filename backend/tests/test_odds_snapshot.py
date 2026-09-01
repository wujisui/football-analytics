"""Pre-match odds clocks: keep frozen boards, skip proven live boards."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.odds_snapshot import (
    annotate_odds_snapshot,
    classify_board_clock,
    is_fixture_prematch,
    normalize_odds_snapshot,
)
from app.services.prematch_package import package_from_record


KICKOFF = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class PrematchGuardTests(unittest.TestCase):
    def test_not_started_before_kickoff_is_prematch(self) -> None:
        now = KICKOFF - timedelta(minutes=5)
        self.assertTrue(
            is_fixture_prematch(
                match_start_time=KICKOFF,
                now=now,
            )
        )

    def test_local_status_does_not_override_list_time_boundary(self) -> None:
        self.assertTrue(
            is_fixture_prematch(
                match_start_time=KICKOFF,
                now=KICKOFF - timedelta(hours=1),
            )
        )
        self.assertFalse(
            is_fixture_prematch(
                match_start_time=KICKOFF,
                now=KICKOFF + timedelta(seconds=1),
            )
        )


class NormalizeSnapshotTests(unittest.TestCase):
    def test_live_board_is_skipped(self) -> None:
        board = {
            "available": True,
            "captured_at": _iso(KICKOFF + timedelta(minutes=12)),
            "match_winner": {"home": "1.80", "draw": "3.40", "away": "4.20"},
        }
        result = normalize_odds_snapshot(
            board,
            match_start_time=KICKOFF,
            fixture_id=1,
            log_invalid=False,
        )
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("invalid_reason"), "live_odds")
        self.assertTrue(result.get("is_live"))

    def test_legacy_board_without_clock_stays_available(self) -> None:
        board = {
            "available": True,
            "match_winner": {"home": "1.80", "draw": "3.40", "away": "4.20"},
        }
        result = normalize_odds_snapshot(
            board,
            match_start_time=KICKOFF,
            fixture_id=1,
            log_invalid=False,
        )
        self.assertTrue(result.get("available"))
        self.assertFalse(result.get("is_live"))
        self.assertEqual(classify_board_clock(board, match_start_time=KICKOFF), "ok")

    def test_prematch_board_is_annotated(self) -> None:
        scraped = KICKOFF - timedelta(hours=3)
        board = annotate_odds_snapshot(
            {"available": True, "match_winner": {"home": "1.90"}},
            scraped_at=scraped,
            match_start_time=KICKOFF,
            role="current",
        )
        self.assertEqual(board["scraped_at"], _iso(scraped))
        self.assertEqual(board["captured_at"], _iso(scraped))
        self.assertEqual(board["match_start_time"], _iso(KICKOFF))
        self.assertFalse(board["is_live"])
        self.assertTrue(board["valid"])


class PackageFromRecordTests(unittest.TestCase):
    def test_live_current_board_is_hidden_from_analysis(self) -> None:
        import json

        stored = MagicMock()
        stored.fixture_id = 9
        stored.fixture = MagicMock(date=KICKOFF)
        stored.odds_json = json.dumps(
            {
                "available": True,
                "captured_at": _iso(KICKOFF + timedelta(minutes=8)),
                "match_winner": {"home": "1.5", "draw": "4.0", "away": "6.0"},
            }
        )
        stored.odds_opening_json = json.dumps(
            {
                "available": True,
                "captured_at": _iso(KICKOFF - timedelta(hours=20)),
                "match_winner": {"home": "1.7", "draw": "3.8", "away": "5.0"},
            }
        )
        stored.odds_mid_json = None
        stored.odds_late_json = None
        stored.lineups_json = None
        stored.injuries_json = None
        stored.briefing_json = None
        stored.h2h_json = None
        stored.home_form_json = None
        stored.away_form_json = None
        stored.standings_json = None
        stored.home_formation = None
        stored.away_formation = None

        package = package_from_record(stored, match_start_time=KICKOFF)
        self.assertFalse(package["odds"].get("available"))
        self.assertTrue(package["odds_opening"].get("available"))


class CollectPackageFrozenBoardTests(unittest.IsolatedAsyncioTestCase):
    async def test_enriched_package_keeps_frozen_opening_board(self) -> None:
        """补包只拉即时盘：冻结的初盘必须从本地行带进展示包。"""
        import json

        from app.services.analyzer import AnalyzerService

        stored = MagicMock()
        stored.fixture_id = 77
        stored.fixture = MagicMock(date=KICKOFF)
        stored.odds_json = None
        stored.odds_opening_json = json.dumps(
            {
                "available": True,
                "captured_at": _iso(KICKOFF - timedelta(days=1)),
                "match_winner": {"home": "1.97", "draw": "3.50", "away": "3.60"},
            }
        )
        for attr in (
            "odds_mid_json",
            "odds_late_json",
            "lineups_json",
            "injuries_json",
            "briefing_json",
            "h2h_json",
            "home_form_json",
            "away_form_json",
            "standings_json",
            "home_formation",
            "away_formation",
        ):
            setattr(stored, attr, None)

        service = AnalyzerService.__new__(AnalyzerService)
        service.session = AsyncMock()
        service.cache = MagicMock()
        service._get_stored_pre_match_row = AsyncMock(return_value=stored)
        service._fetch_odds_for_package = AsyncMock()

        fixture = SimpleNamespace(
            id=77,
            league_id=39,
            home_team_id=1,
            away_team_id=2,
            date=KICKOFF,
            league=SimpleNamespace(name="英超", season="2026"),
        )

        with patch(
            "app.services.analyzer.resolve_fixture_standings",
            AsyncMock(return_value={"available": True, "fetched": True}),
        ):
            package = await AnalyzerService._collect_prematch_package(
                service, AsyncMock(), fixture, 60
            )

        self.assertTrue(package["odds_opening"].get("available"))
        self.assertFalse(package["odds"].get("available"))


class RefreshGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_skips_official_pull_after_kickoff(self) -> None:
        from app.services.fetcher import FootballFetcher

        fixture = MagicMock()
        fixture.league_id = 39
        fixture.status = "pending"
        fixture.date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        league = MagicMock(is_catalog=True)
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[fixture, league])
        fetcher = FootballFetcher.__new__(FootballFetcher)
        fetcher.session = session
        fetcher.cache = MagicMock()
        fetcher._fetch_odds_with_rate_limit = AsyncMock()

        updated = await FootballFetcher.refresh_odds_for_fixture(fetcher, 42)
        self.assertFalse(updated)
        fetcher._fetch_odds_with_rate_limit.assert_not_awaited()

    async def test_refresh_skips_future_fixture_outside_catalog(self) -> None:
        from app.services.fetcher import FootballFetcher

        fixture = MagicMock(
            league_id=999,
            date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2),
        )
        league = MagicMock(is_catalog=False)
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[fixture, league])
        fetcher = FootballFetcher.__new__(FootballFetcher)
        fetcher.session = session
        fetcher.cache = MagicMock()
        fetcher._fetch_odds_with_rate_limit = AsyncMock()

        updated = await FootballFetcher.refresh_odds_for_fixture(fetcher, 43)
        self.assertFalse(updated)
        fetcher._fetch_odds_with_rate_limit.assert_not_awaited()

    async def test_refresh_skips_fixture_not_on_current_match_day(self) -> None:
        from app.services.fetcher import FootballFetcher

        fixture = MagicMock()
        fixture.league_id = 39
        fixture.date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            hours=2
        )
        fixture.match_day = "2026-08-30"
        league = MagicMock(is_catalog=True)
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[fixture, league])
        fetcher = FootballFetcher.__new__(FootballFetcher)
        fetcher.session = session
        fetcher.cache = MagicMock()
        fetcher._fetch_odds_with_rate_limit = AsyncMock()

        with (
            patch(
                "app.services.league_catalog.allowed_league_ids",
                AsyncMock(return_value={39}),
            ),
            patch(
                "app.services.match_day.current_prematch_match_day",
                AsyncMock(return_value="2026-08-29"),
            ),
        ):
            updated = await FootballFetcher.refresh_odds_for_fixture(fetcher, 44)

        self.assertFalse(updated)
        fetcher._fetch_odds_with_rate_limit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
