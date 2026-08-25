import json
import unittest
from types import SimpleNamespace

from app.services.prematch_package import parse_odds_payload, rehydrate_odds_markets


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

        current = _odds_snippet_from_stored(stored)
        opening = _odds_snippet_from_stored(stored, opening=True)

        self.assertEqual(current.asian_handicap.line, "-0.5")
        self.assertEqual(opening.asian_handicap.line, "-0.25")
        # List cards label each board with its own capture time.
        self.assertEqual(current.captured_at, "2026-08-25T01:00:00Z")
        self.assertEqual(opening.captured_at, "2026-08-23T03:00:00Z")


if __name__ == "__main__":
    unittest.main()
