"""Kickoff-time boundary: 已开赛的场次离开未开赛列表，进入赛果列表。"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.fixture import Fixture
from app.services.results_capture import (
    LIVE_SCORE_REFRESH_HOURS,
    SETTLE_SCORE_REFRESH_DAYS,
    prematch_list_clause,
    results_list_clause,
    results_list_score,
    score_refresh_ttl,
)
from app.services.ttl_policy import TTL_FIXTURE_LIVE_SCORE, TTL_FIXTURE_SETTLE_SCORE

NOW = datetime(2026, 8, 11, 1, 53)  # 北京时间 09:53
KICKED_OFF = NOW - timedelta(hours=1, minutes=38)
UPCOMING = NOW + timedelta(hours=3)


def _sql(clause) -> str:
    stmt = select(Fixture.id).where(clause)
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def test_list_membership_depends_only_on_kickoff_time() -> None:
    prematch = _sql(prematch_list_clause(NOW))
    results = _sql(results_list_clause(NOW))
    # 本地 status 可能仍是 pending；列表归属只比较服务器时间与开赛时刻。
    assert "fixtures.date > '2026-08-11 01:53:00'" in prematch
    assert "fixtures.date <= '2026-08-11 01:53:00'" in results
    assert "fixtures.status" not in prematch
    assert "fixtures.status" not in results


def test_live_score_refresh_only_for_started_unfinished_fixtures() -> None:
    assert score_refresh_ttl("pending", KICKED_OFF, NOW) == TTL_FIXTURE_LIVE_SCORE
    assert score_refresh_ttl("live", KICKED_OFF, NOW) == TTL_FIXTURE_LIVE_SCORE
    assert score_refresh_ttl("pending", UPCOMING, NOW) is None
    assert score_refresh_ttl("finished", KICKED_OFF, NOW) is None
    assert score_refresh_ttl("postponed", KICKED_OFF, NOW) is None


def test_long_unsettled_fixture_still_gets_one_low_frequency_settle_call() -> None:
    # 定时回写被配额挤掉时，赛果页不该一直停在「进行中」。
    stale = NOW - timedelta(hours=LIVE_SCORE_REFRESH_HOURS + 7)
    assert score_refresh_ttl("pending", stale, NOW) == TTL_FIXTURE_SETTLE_SCORE
    ancient = NOW - timedelta(days=SETTLE_SCORE_REFRESH_DAYS, hours=1)
    assert score_refresh_ttl("pending", ancient, NOW) is None


def test_unfinished_result_list_uses_zero_score_placeholder() -> None:
    assert results_list_score("pending", None, None) == (0, 0)
    assert results_list_score("live", None, 1) == (0, 0)
    assert results_list_score("live", 1, 2) == (1, 2)
    assert results_list_score("finished", None, None) == (None, None)


def test_kickoff_with_offset_is_compared_in_utc() -> None:
    aware = KICKED_OFF.replace(tzinfo=timezone.utc)
    assert score_refresh_ttl("pending", aware, NOW) == TTL_FIXTURE_LIVE_SCORE
