"""Parse and assemble pre-match package (odds / lineups / injuries / H2H / form)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.api_utils import extract_items, first_value

logger = logging.getLogger(__name__)


def dumps_json(data: Any) -> str | None:
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False, default=str)


def loads_json(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in pre_match_data field")
        return default


def parse_match_result_for_team(item: dict[str, Any], team_id: int) -> str | None:
    home_id = first_value(item, [["teams", "home", "id"], ["homeTeam", "id"]])
    away_id = first_value(item, [["teams", "away", "id"], ["awayTeam", "id"]])
    home_goals = first_value(item, [["goals", "home"], ["score", "home"]])
    away_goals = first_value(item, [["goals", "away"], ["score", "away"]])
    if None in (home_id, away_id, home_goals, away_goals):
        return None
    home_goals = int(home_goals)
    away_goals = int(away_goals)
    if int(home_id) == team_id:
        if home_goals > away_goals:
            return "W"
        if home_goals == away_goals:
            return "D"
        return "L"
    if int(away_id) == team_id:
        if away_goals > home_goals:
            return "W"
        if away_goals == home_goals:
            return "D"
        return "L"
    return None


def summarize_form_payload(payload: dict[str, Any], team_id: int, limit: int = 5) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    finished = {"FT", "AET", "PEN"}
    for item in extract_items(payload):
        status = first_value(item, [["fixture", "status", "short"], ["status", "short"], ["status"]])
        if status and str(status).upper() not in finished:
            continue
        result = parse_match_result_for_team(item, team_id)
        if result is None:
            continue
        matches.append(
            {
                "fixture_id": first_value(item, [["fixture", "id"], ["id"]]),
                "date": first_value(item, [["fixture", "date"], ["date"]]),
                "home": first_value(item, [["teams", "home", "name"], ["homeTeam", "name"]], ""),
                "away": first_value(item, [["teams", "away", "name"], ["awayTeam", "name"]], ""),
                "score": (
                    f"{first_value(item, [['goals', 'home'], ['score', 'home']], '-')}"
                    f"-{first_value(item, [['goals', 'away'], ['score', 'away']], '-')}"
                ),
                "result": result,
            }
        )
        if len(matches) >= limit:
            break

    wins = sum(1 for m in matches if m["result"] == "W")
    draws = sum(1 for m in matches if m["result"] == "D")
    losses = sum(1 for m in matches if m["result"] == "L")
    return {
        "team_id": team_id,
        "played": len(matches),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "form": "".join(m["result"] for m in matches),
        "matches": matches,
    }


def summarize_h2h_payload(payload: dict[str, Any], home_team_id: int, limit: int = 5) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    finished = {"FT", "AET", "PEN"}
    home_wins = draws = away_wins = 0

    for item in extract_items(payload):
        status = first_value(item, [["fixture", "status", "short"], ["status", "short"], ["status"]])
        if status and str(status).upper() not in finished:
            continue
        home_goals = first_value(item, [["goals", "home"], ["score", "home"]])
        away_goals = first_value(item, [["goals", "away"], ["score", "away"]])
        if home_goals is None or away_goals is None:
            continue
        home_goals = int(home_goals)
        away_goals = int(away_goals)
        if home_goals > away_goals:
            # relative to fixture home team in that match, not our fixture home
            fixture_home_id = first_value(item, [["teams", "home", "id"]])
            if fixture_home_id is not None and int(fixture_home_id) == home_team_id:
                home_wins += 1
                outcome = "home"
            else:
                away_wins += 1
                outcome = "away"
        elif home_goals == away_goals:
            draws += 1
            outcome = "draw"
        else:
            fixture_home_id = first_value(item, [["teams", "home", "id"]])
            if fixture_home_id is not None and int(fixture_home_id) == home_team_id:
                away_wins += 1
                outcome = "away"
            else:
                home_wins += 1
                outcome = "home"

        matches.append(
            {
                "fixture_id": first_value(item, [["fixture", "id"], ["id"]]),
                "date": first_value(item, [["fixture", "date"], ["date"]]),
                "home": first_value(item, [["teams", "home", "name"]], ""),
                "away": first_value(item, [["teams", "away", "name"]], ""),
                "score": f"{home_goals}-{away_goals}",
                "outcome_for_current_home": outcome,
            }
        )
        if len(matches) >= limit:
            break

    return {
        "played": len(matches),
        "home_wins": home_wins,
        "draws": draws,
        "away_wins": away_wins,
        "matches": matches,
    }


def parse_odds_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract Match Winner (1X2) odds from first bookmaker when available."""
    bookmakers_out: list[dict[str, Any]] = []
    match_winner: dict[str, Any] | None = None

    for item in extract_items(payload):
        bookmakers = item.get("bookmakers") or []
        for book in bookmakers:
            book_name = first_value(book, [["name"], ["bookmaker", "name"]], "unknown")
            bets = book.get("bets") or []
            for bet in bets:
                bet_name = str(first_value(bet, [["name"], ["label"]], "")).lower()
                values = bet.get("values") or []
                parsed_values = [
                    {
                        "label": first_value(v, [["value"], ["label"]], ""),
                        "odd": first_value(v, [["odd"], ["odds"]], None),
                    }
                    for v in values
                ]
                entry = {
                    "bookmaker": book_name,
                    "bet": first_value(bet, [["name"], ["label"]], ""),
                    "values": parsed_values,
                }
                if "match winner" in bet_name or bet_name in {"1x2", "winner", "full time result"}:
                    if match_winner is None:
                        match_winner = {
                            "bookmaker": book_name,
                            "home": None,
                            "draw": None,
                            "away": None,
                            "values": parsed_values,
                        }
                        for v in parsed_values:
                            label = str(v.get("label", "")).lower()
                            odd = v.get("odd")
                            if label in {"home", "1"}:
                                match_winner["home"] = odd
                            elif label in {"draw", "x"}:
                                match_winner["draw"] = odd
                            elif label in {"away", "2"}:
                                match_winner["away"] = odd
                bookmakers_out.append(entry)
            if match_winner is not None:
                break
        if match_winner is not None:
            break

    return {
        "match_winner": match_winner,
        "bookmakers": bookmakers_out[:5],
        "available": match_winner is not None or bool(bookmakers_out),
    }


def _parse_player(player_block: dict[str, Any]) -> dict[str, Any]:
    player = player_block.get("player") if isinstance(player_block.get("player"), dict) else player_block
    return {
        "id": first_value(player, [["id"], ["player", "id"]]),
        "name": first_value(player, [["name"], ["player", "name"]], ""),
        "number": first_value(player_block, [["player", "number"], ["number"]], None),
        "pos": first_value(player_block, [["player", "pos"], ["pos"]], None),
        "grid": first_value(player_block, [["player", "grid"], ["grid"]], None),
    }


def parse_lineups_payload(payload: dict[str, Any]) -> dict[str, Any]:
    teams: list[dict[str, Any]] = []
    for item in extract_items(payload):
        team_id = first_value(item, [["team", "id"]])
        start_xi = [_parse_player(p) for p in (item.get("startXI") or item.get("start_xi") or [])]
        substitutes = [_parse_player(p) for p in (item.get("substitutes") or [])]
        teams.append(
            {
                "team_id": int(team_id) if team_id is not None else None,
                "team_name": first_value(item, [["team", "name"]], ""),
                "formation": first_value(item, [["formation"], ["team", "formation"]], None),
                "coach": first_value(item, [["coach", "name"]], None),
                "start_xi": start_xi,
                "substitutes": substitutes,
            }
        )

    home = teams[0] if teams else None
    away = teams[1] if len(teams) > 1 else None
    return {
        "home": home,
        "away": away,
        "available": bool(teams),
    }


def parse_injuries_payload(
    payload: dict[str, Any],
    home_team_id: int,
    away_team_id: int,
) -> dict[str, Any]:
    home: list[dict[str, Any]] = []
    away: list[dict[str, Any]] = []

    for item in extract_items(payload):
        team_id = first_value(item, [["team", "id"]])
        if team_id is None:
            continue
        entry = {
            "player_id": first_value(item, [["player", "id"]]),
            "player_name": first_value(item, [["player", "name"]], ""),
            "type": first_value(item, [["player", "type"], ["type"]], None),
            "reason": first_value(item, [["player", "reason"], ["reason"]], None),
        }
        if int(team_id) == home_team_id:
            home.append(entry)
        elif int(team_id) == away_team_id:
            away.append(entry)

    return {
        "home": home,
        "away": away,
        "available": bool(home or away),
    }


def package_from_record(record: Any) -> dict[str, Any]:
    """Build API package dict from PreMatchData ORM row."""
    lineups = loads_json(getattr(record, "lineups_json", None), {})
    injuries = loads_json(getattr(record, "injuries_json", None), {})
    return {
        "odds": loads_json(getattr(record, "odds_json", None), {"available": False}),
        "lineups": lineups if lineups else {"available": False, "home": None, "away": None},
        "injuries": injuries if injuries else {"available": False, "home": [], "away": []},
        "head_to_head": loads_json(getattr(record, "h2h_json", None), {"played": 0, "matches": []}),
        "home_form": loads_json(getattr(record, "home_form_json", None), {"played": 0, "matches": []}),
        "away_form": loads_json(getattr(record, "away_form_json", None), {"played": 0, "matches": []}),
        "home_formation": getattr(record, "home_formation", None)
        or (lineups.get("home") or {}).get("formation"),
        "away_formation": getattr(record, "away_formation", None)
        or (lineups.get("away") or {}).get("formation"),
    }
