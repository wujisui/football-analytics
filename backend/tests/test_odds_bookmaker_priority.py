import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.prematch_package import (
    parse_odds_payload,
    rehydrate_odds_markets,
    should_write_opening,
)

_MATCH_WINNER = {
    "name": "Match Winner",
    "values": [
        {"value": "Home", "odd": "2.50"},
        {"value": "Draw", "odd": "2.90"},
        {"value": "Away", "odd": "2.88"},
    ],
}
_ASIAN_HANDICAP = {
    "name": "Asian Handicap",
    "values": [
        {"value": "Home 0", "odd": "1.80"},
        {"value": "Away 0", "odd": "2.06"},
    ],
}
_GOALS_OU = {
    "name": "Goals Over/Under",
    "values": [
        {"value": "Over 2.25", "odd": "2.05"},
        {"value": "Under 2.25", "odd": "1.81"},
    ],
}


def _bookmaker(name: str, home_odd: str) -> dict:
    return {
        "name": name,
        "bets": [
            {
                "name": "Match Winner",
                "values": [
                    {"value": "Home", "odd": home_odd},
                    {"value": "Draw", "odd": "3.20"},
                    {"value": "Away", "odd": "4.10"},
                ],
            },
            {
                "name": "Asian Handicap",
                "values": [
                    {"value": "Home -0.5", "odd": "1.90"},
                    {"value": "Away -0.5", "odd": "1.95"},
                ],
            },
            {
                "name": "Goals Over/Under",
                "values": [
                    {"value": "Over 2.5", "odd": "1.85"},
                    {"value": "Under 2.5", "odd": "2.00"},
                ],
            },
            {
                "name": "Both Teams Score",
                "values": [
                    {"value": "Yes", "odd": "1.80"},
                    {"value": "No", "odd": "2.05"},
                ],
            },
        ],
    }


class OddsBookmakerPriorityTests(unittest.TestCase):
    def test_pinnacle_is_selected_even_when_10bet_is_returned_first(self) -> None:
        payload = {
            "response": [
                {
                    "bookmakers": [
                        _bookmaker("10Bet", "2.10"),
                        _bookmaker("Pinnacle", "2.25"),
                    ]
                }
            ]
        }

        parsed = parse_odds_payload(payload)

        self.assertEqual(parsed["match_winner"]["bookmaker"], "Pinnacle")
        self.assertEqual(parsed["match_winner"]["home"], "2.25")
        self.assertEqual(parsed["asian_handicap"]["bookmaker"], "Pinnacle")
        self.assertEqual(parsed["goals_ou"]["bookmaker"], "Pinnacle")
        self.assertEqual(parsed["both_teams_score"]["bookmaker"], "Pinnacle")

    def test_sbo_is_used_when_pinnacle_is_unavailable(self) -> None:
        payload = {
            "response": [
                {
                    "bookmakers": [
                        _bookmaker("10Bet", "2.10"),
                        _bookmaker("SBO", "2.20"),
                    ]
                }
            ]
        }

        parsed = parse_odds_payload(payload)

        self.assertEqual(parsed["match_winner"]["bookmaker"], "SBO")
        self.assertEqual(parsed["match_winner"]["home"], "2.20")


class SingleBookmakerBoardTests(unittest.TestCase):
    """一份盘口只能出自一家庄：混庄会让「初盘 0 → 即时盘 -1」看起来像假的盘口移动。"""

    def _payload(self, books: list[dict]) -> dict:
        return {"response": [{"bookmakers": books}]}

    def test_sharper_book_with_only_1x2_does_not_split_the_board(self) -> None:
        # 开赛前一周 Pinnacle 未开盘，William Hill 只挂胜平负，1xBet 三个玩法都有。
        parsed = parse_odds_payload(
            self._payload(
                [
                    {"name": "William Hill", "bets": [_MATCH_WINNER]},
                    {
                        "name": "1xBet",
                        "bets": [_MATCH_WINNER, _ASIAN_HANDICAP, _GOALS_OU],
                    },
                ]
            )
        )

        self.assertEqual(parsed["bookmaker"], "1xBet")
        self.assertEqual(parsed["match_winner"]["bookmaker"], "1xBet")
        self.assertEqual(parsed["asian_handicap"]["bookmaker"], "1xBet")
        self.assertEqual(parsed["goals_ou"]["bookmaker"], "1xBet")

    def test_market_missing_from_the_primary_book_still_falls_back(self) -> None:
        parsed = parse_odds_payload(
            self._payload(
                [
                    {"name": "Pinnacle", "bets": [_MATCH_WINNER, _ASIAN_HANDICAP]},
                    {"name": "1xBet", "bets": [_GOALS_OU]},
                ]
            )
        )

        self.assertEqual(parsed["bookmaker"], "Pinnacle")
        self.assertEqual(parsed["asian_handicap"]["bookmaker"], "Pinnacle")
        self.assertEqual(parsed["goals_ou"]["bookmaker"], "1xBet")

    def test_truncated_bookmaker_rows_do_not_re_mix_the_board_on_read(self) -> None:
        """存储只留 12 条明细，主庄的核心玩法必须在里面，否则每次读又拼回两家。"""
        filler = {
            "name": "10Bet",
            "bets": [
                {
                    "name": f"Filler Market {i}",
                    "values": [{"value": "Yes", "odd": "1.50"}],
                }
                for i in range(12)
            ],
        }
        parsed = parse_odds_payload(
            self._payload(
                [
                    {"name": "William Hill", "bets": [_MATCH_WINNER]},
                    {
                        "name": "1xBet",
                        "bets": [_MATCH_WINNER, _ASIAN_HANDICAP, _GOALS_OU],
                    },
                    filler,
                ]
            )
        )
        self.assertEqual(parsed["bookmaker"], "1xBet")
        self.assertEqual(len(parsed["bookmakers"]), 12)

        reread = rehydrate_odds_markets(parsed)
        self.assertEqual(reread["match_winner"]["bookmaker"], "1xBet")
        self.assertEqual(reread["asian_handicap"]["bookmaker"], "1xBet")
        self.assertEqual(reread["goals_ou"]["bookmaker"], "1xBet")


class OpeningUpgradeTests(unittest.TestCase):
    """初盘可由次级庄兜底，但主庄一开盘就要替换，否则两份盘口不同源。"""

    def _board(self, bookmaker: str) -> dict:
        return {"available": True, "bookmaker": bookmaker}

    def test_any_prematch_pull_creates_the_first_opening(self) -> None:
        candidate = self._board("Pinnacle")
        self.assertTrue(should_write_opening({}, candidate, locked=False))
        self.assertFalse(should_write_opening({}, candidate, locked=True))

    def test_sharper_book_replaces_a_fallback_opening_on_any_refresh(self) -> None:
        opening = self._board("1xBet")
        self.assertTrue(
            should_write_opening(
                opening, self._board("Pinnacle"), locked=False
            )
        )
        # 同庄或更次级的盘口不动初盘。
        self.assertFalse(
            should_write_opening(
                opening, self._board("1xBet"), locked=False
            )
        )
        self.assertFalse(
            should_write_opening(
                opening, self._board("10Bet"), locked=False
            )
        )

    def test_opening_is_never_rewritten_after_kickoff(self) -> None:
        self.assertFalse(
            should_write_opening(
                self._board("1xBet"),
                self._board("Pinnacle"),
                locked=True,
            )
        )

    def test_legacy_openings_without_a_top_level_bookmaker_still_upgrade(self) -> None:
        legacy = {"available": True, "match_winner": {"bookmaker": "William Hill"}}
        self.assertTrue(
            should_write_opening(
                legacy, self._board("Pinnacle"), locked=False
            )
        )
        self.assertFalse(
            should_write_opening(
                legacy, self._board("10Bet"), locked=False
            )
        )

    def test_empty_board_never_becomes_the_opening(self) -> None:
        self.assertFalse(
            should_write_opening({}, {"available": False}, locked=False)
        )


class FullMatchBoardTests(unittest.TestCase):
    """半场 / 组合盘不能当主盘：否则推荐 小(2.25) 会配上半场 0.5 的玩法行。"""

    def _payload(self, bets: list[dict]) -> dict:
        return {"response": [{"bookmakers": [{"name": "William Hill", "bets": bets}]}]}

    def test_half_time_boards_never_become_main_lines(self) -> None:
        parsed = parse_odds_payload(
            self._payload(
                [
                    {
                        "name": "Goals Over/Under First Half",
                        "values": [
                            {"value": "Over 0.5", "odd": "1.44"},
                            {"value": "Under 0.5", "odd": "2.62"},
                        ],
                    },
                    {
                        "name": "Goals Over/Under",
                        "values": [
                            {"value": "Over 2.25", "odd": "2.05"},
                            {"value": "Under 2.25", "odd": "1.81"},
                        ],
                    },
                    {
                        "name": "Asian Handicap First Half",
                        "values": [
                            {"value": "Home -0.25", "odd": "1.90"},
                            {"value": "Away -0.25", "odd": "1.95"},
                        ],
                    },
                ]
            )
        )

        self.assertEqual(parsed["goals_ou"]["line"], "2.25")
        self.assertEqual(parsed["goals_ou"]["bet"], "Goals Over/Under")
        self.assertIsNone(parsed["asian_handicap"])

    def test_combo_boards_are_not_treated_as_btts(self) -> None:
        parsed = parse_odds_payload(
            self._payload(
                [
                    {
                        "name": "Total Goals/Both Teams To Score",
                        "values": [{"value": "Yes", "odd": "2.40"}],
                    },
                    {
                        "name": "Both Teams To Score in Both Halves",
                        "values": [{"value": "Yes", "odd": "6.00"}],
                    },
                ]
            )
        )

        self.assertIsNone(parsed["both_teams_score"])

    def test_rehydrate_drops_stored_half_time_board(self) -> None:
        stored = {
            "available": True,
            "goals_ou": {
                "bookmaker": "William Hill",
                "bet": "Goals Over/Under First Half",
                "line": "0.5",
                "home": "1.44",
                "away": "2.62",
            },
            "bookmakers": [
                {
                    "bookmaker": "William Hill",
                    "bet": "Goals Over/Under First Half",
                    "values": [
                        {"label": "Over 0.5", "odd": "1.44"},
                        {"label": "Under 0.5", "odd": "2.62"},
                    ],
                }
            ],
        }

        self.assertIsNone(rehydrate_odds_markets(stored)["goals_ou"])

    def test_list_snippet_can_read_current_and_frozen_opening_boards(self) -> None:
        from app.api.v1.endpoints.fixtures import _odds_snippet_from_stored

        def _board(line: str, captured_at: str) -> str:
            return json.dumps(
                {
                    "available": True,
                    "asian_handicap": {
                        "line": line,
                        "home": "1.91",
                        "away": "1.95",
                    },
                    "captured_at": captured_at,
                }
            )

        stored = SimpleNamespace(
            odds_json=_board("-0.5", "2026-08-25T01:00:00Z"),
            odds_opening_json=_board("-0.25", "2026-08-23T03:00:00Z"),
        )
        fixture = SimpleNamespace(
            id=1,
            date=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
        )

        current = _odds_snippet_from_stored(stored, fixture)
        opening = _odds_snippet_from_stored(stored, fixture, opening=True)

        self.assertEqual(current.asian_handicap.line, "-0.5")
        self.assertEqual(opening.asian_handicap.line, "-0.25")
        # List cards label each board with its own capture time.
        self.assertEqual(current.captured_at, "2026-08-25T01:00:00Z")
        self.assertEqual(opening.captured_at, "2026-08-23T03:00:00Z")

    def test_detail_snippet_keeps_captured_at_for_the_list_merge(self) -> None:
        """详情摘要会覆盖列表行；漏掉 captured_at 会让列表把两份盘口并成一份。"""
        from app.api.v1.endpoints.fixtures import _odds_snippet_from_package

        snippet = _odds_snippet_from_package(
            {
                "available": True,
                "asian_handicap": {"line": "-1", "home": "2.03", "away": "1.85"},
                "captured_at": "2026-08-25T06:06:25Z",
            }
        )

        assert snippet is not None
        self.assertEqual(snippet.captured_at, "2026-08-25T06:06:25Z")
        self.assertIsNone(_odds_snippet_from_package({"available": False}))
        self.assertIsNone(_odds_snippet_from_package(None))


if __name__ == "__main__":
    unittest.main()
