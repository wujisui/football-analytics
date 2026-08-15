"""Settlement readiness after detail score refresh."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.results_accuracy import fixture_ready_to_grade
from app.services.ttl_policy import detail_package_frozen

NOW = datetime(2026, 8, 15, 6, 51)
KICKED_OFF = NOW - timedelta(hours=14)
UPCOMING = NOW + timedelta(hours=3)
FROZEN_SNAPSHOT = SimpleNamespace(recommendation="胜")
NO_SNAPSHOT = SimpleNamespace(recommendation="待分析")


def test_finished_status_with_score_is_gradable() -> None:
    fx = SimpleNamespace(status="finished", status_short="FT", home_goals=2, away_goals=2)
    assert fixture_ready_to_grade(fx) is True


def test_live_status_with_ft_short_and_score_is_gradable() -> None:
    # Detail refresh wrote FT board; long-form status may still say live.
    fx = SimpleNamespace(status="live", status_short="FT", home_goals=0, away_goals=5)
    assert fixture_ready_to_grade(fx) is True


def test_live_without_final_short_is_not_gradable() -> None:
    fx = SimpleNamespace(status="live", status_short="2H", home_goals=1, away_goals=0)
    assert fixture_ready_to_grade(fx) is False


def test_finished_without_score_is_not_gradable() -> None:
    fx = SimpleNamespace(status="finished", status_short="FT", home_goals=None, away_goals=None)
    assert fixture_ready_to_grade(fx) is False


def test_started_fixture_with_frozen_snapshot_reads_package_locally() -> None:
    # 配额只够结算：展示包不再补拉，官方这趟只补比分与状态。
    assert detail_package_frozen(KICKED_OFF, "pending", FROZEN_SNAPSHOT, NOW) is True
    assert detail_package_frozen(KICKED_OFF, "finished", FROZEN_SNAPSHOT, NOW) is True


def test_prematch_and_never_analyzed_fixtures_still_enrich() -> None:
    assert detail_package_frozen(UPCOMING, "pending", FROZEN_SNAPSHOT, NOW) is False
    assert detail_package_frozen(KICKED_OFF, "pending", NO_SNAPSHOT, NOW) is False
    assert detail_package_frozen(KICKED_OFF, "pending", None, NOW) is False
