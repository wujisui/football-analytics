import unittest

from app.services.prematch_package import parse_odds_payload


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


if __name__ == "__main__":
    unittest.main()
