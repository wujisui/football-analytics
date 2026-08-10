"""Tests for shared league standings parsing / rank snippets."""

from app.services.league_standings import parse_standings_table, snippet_from_ranks


def test_parse_standings_table_and_snippet() -> None:
    payload = {
        "response": [
            {
                "league": {
                    "id": 172,
                    "name": "First League",
                    "standings": [
                        [
                            {"rank": 9, "team": {"id": 854}, "group": "Regular Season"},
                            {"rank": 11, "team": {"id": 859}, "group": "Regular Season"},
                            {"rank": 3, "team": {"id": 634}},
                        ]
                    ],
                }
            }
        ]
    }
    table = parse_standings_table(payload, league_id=172, league_name="First League")
    assert table["available"] is True
    assert table["by_team_id"]["854"]["rank"] == 9
    assert table["by_team_id"]["859"]["rank"] == 11

    snippet = snippet_from_ranks(table, 859, 854, league_id=172)
    assert snippet["home_rank"] == 11
    assert snippet["away_rank"] == 9
    assert snippet["available"] is True
    assert snippet["group"] == "Regular Season"
