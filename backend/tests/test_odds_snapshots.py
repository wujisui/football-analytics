"""Kickoff-relative mid / late odds snapshots tagged from existing refreshes."""

import unittest
from datetime import datetime, timedelta, timezone

from app.services.prematch_package import (
    SNAPSHOT_LATE,
    SNAPSHOT_MID,
    hours_before_kickoff,
    should_write_timed_snapshot,
)


def _kickoff() -> datetime:
    return datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def _captured(hours_before: float) -> str:
    at = _kickoff() - timedelta(hours=hours_before)
    return at.isoformat().replace("+00:00", "Z")


def _board(hours_before: float) -> dict:
    return {"available": True, "captured_at": _captured(hours_before)}


def _args(spec: dict, board: dict, *, existing: dict | None = None, locked: bool = False) -> dict:
    return {
        "existing": existing or {},
        "candidate": board,
        "kickoff": _kickoff(),
        "captured_at": board["captured_at"],
        "target_hours": spec["target_hours"],
        "min_hours": spec["min_hours"],
        "max_hours": spec["max_hours"],
        "locked": locked,
        "policy": spec["policy"],
    }


class TimedSnapshotWindowTests(unittest.TestCase):
    def test_hours_before_kickoff_parses_zulu(self) -> None:
        hours = hours_before_kickoff(_kickoff(), _captured(6.0))
        self.assertAlmostEqual(hours or 0.0, 6.0, places=5)

    def test_mid_keeps_the_capture_closest_to_six_hours(self) -> None:
        first = _board(8.5)
        self.assertTrue(should_write_timed_snapshot(**_args(SNAPSHOT_MID, first)))
        closer = _board(6.2)
        self.assertTrue(
            should_write_timed_snapshot(**_args(SNAPSHOT_MID, closer, existing=first))
        )
        farther = _board(9.5)
        self.assertFalse(
            should_write_timed_snapshot(**_args(SNAPSHOT_MID, farther, existing=closer))
        )

    def test_t_minus_three_hours_belongs_to_late_not_mid(self) -> None:
        board = _board(3.0)
        self.assertFalse(should_write_timed_snapshot(**_args(SNAPSHOT_MID, board)))
        self.assertTrue(should_write_timed_snapshot(**_args(SNAPSHOT_LATE, board)))

    def test_late_keeps_the_newest_capture_in_the_window(self) -> None:
        first = _board(2.5)
        self.assertTrue(should_write_timed_snapshot(**_args(SNAPSHOT_LATE, first)))
        newer = _board(0.4)
        self.assertTrue(
            should_write_timed_snapshot(**_args(SNAPSHOT_LATE, newer, existing=first))
        )
        older = _board(1.8)
        self.assertFalse(
            should_write_timed_snapshot(**_args(SNAPSHOT_LATE, older, existing=newer))
        )

    def test_outside_window_and_after_kickoff_are_ignored(self) -> None:
        too_early = _board(20.0)
        self.assertFalse(should_write_timed_snapshot(**_args(SNAPSHOT_MID, too_early)))
        after = _board(-0.5)
        self.assertFalse(should_write_timed_snapshot(**_args(SNAPSHOT_LATE, after)))

    def test_locked_rows_do_not_rewrite_snapshots(self) -> None:
        board = _board(0.5)
        self.assertFalse(
            should_write_timed_snapshot(**_args(SNAPSHOT_LATE, board, locked=True))
        )


if __name__ == "__main__":
    unittest.main()
