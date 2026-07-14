"""Parse and assemble pre-match package (odds / lineups / injuries / H2H / form / briefing)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.services.api_utils import extract_items, first_value
from app.services.team_names import localize_match_teams, localize_matches_block

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


def summarize_form_payload(payload: dict[str, Any], team_id: int, limit: int = 20) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    finished = {"FT", "AET", "PEN"}
    for item in extract_items(payload):
        status = first_value(item, [["fixture", "status", "short"], ["status", "short"], ["status"]])
        if status and str(status).upper() not in finished:
            continue
        result = parse_match_result_for_team(item, team_id)
        if result is None:
            continue
        ht_home = first_value(item, [["score", "halftime", "home"]])
        ht_away = first_value(item, [["score", "halftime", "away"]])
        score_ht = (
            f"{ht_home}-{ht_away}"
            if ht_home is not None and ht_away is not None
            else None
        )
        home_id = first_value(item, [["teams", "home", "id"], ["homeTeam", "id"]])
        away_id = first_value(item, [["teams", "away", "id"], ["awayTeam", "id"]])
        home_name = first_value(item, [["teams", "home", "name"], ["homeTeam", "name"]], "")
        away_name = first_value(item, [["teams", "away", "name"], ["awayTeam", "name"]], "")
        matches.append(
            localize_match_teams(
                {
                    "fixture_id": first_value(item, [["fixture", "id"], ["id"]]),
                    "date": first_value(item, [["fixture", "date"], ["date"]]),
                    "home": home_name or "",
                    "away": away_name or "",
                    "home_id": home_id,
                    "away_id": away_id,
                    "score": (
                        f"{first_value(item, [['goals', 'home'], ['score', 'home']], '-')}"
                        f"-{first_value(item, [['goals', 'away'], ['score', 'away']], '-')}"
                    ),
                    "score_ht": score_ht,
                    "league_id": first_value(item, [["league", "id"]]),
                    "league_name": first_value(item, [["league", "name"]], "") or "",
                    "league_country": first_value(item, [["league", "country"]], "") or "",
                    "result": result,
                }
            )
        )

    # Season payloads are chronological; keep the most recent finished matches.
    matches.sort(key=lambda m: str(m.get("date") or ""), reverse=True)
    matches = matches[:limit]

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
        "source": get_settings().history_source_tag,
    }


def summarize_h2h_payload(payload: dict[str, Any], home_team_id: int, limit: int = 20) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    finished = {"FT", "AET", "PEN"}

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
        # Outcome relative to *current fixture* home team, not the H2H match's home side.
        fixture_home_id = first_value(item, [["teams", "home", "id"]])
        current_was_home = fixture_home_id is not None and int(fixture_home_id) == home_team_id
        if home_goals > away_goals:
            outcome = "home" if current_was_home else "away"
        elif home_goals == away_goals:
            outcome = "draw"
        else:
            outcome = "away" if current_was_home else "home"

        ht_home = first_value(item, [["score", "halftime", "home"]])
        ht_away = first_value(item, [["score", "halftime", "away"]])
        score_ht = (
            f"{ht_home}-{ht_away}"
            if ht_home is not None and ht_away is not None
            else None
        )
        matches.append(
            localize_match_teams(
                {
                    "fixture_id": first_value(item, [["fixture", "id"], ["id"]]),
                    "date": first_value(item, [["fixture", "date"], ["date"]]),
                    "home": first_value(item, [["teams", "home", "name"]], "") or "",
                    "away": first_value(item, [["teams", "away", "name"]], "") or "",
                    "home_id": first_value(item, [["teams", "home", "id"]]),
                    "away_id": first_value(item, [["teams", "away", "id"]]),
                    "score": f"{home_goals}-{away_goals}",
                    "score_ht": score_ht,
                    "league_id": first_value(item, [["league", "id"]]),
                    "league_name": first_value(item, [["league", "name"]], "") or "",
                    "league_country": first_value(item, [["league", "country"]], "") or "",
                    "outcome_for_current_home": outcome,
                    "result": (
                        "W"
                        if outcome == "home"
                        else "L"
                        if outcome == "away"
                        else "D"
                    ),
                }
            )
        )

    matches.sort(key=lambda m: str(m.get("date") or ""), reverse=True)
    matches = matches[:limit]
    home_wins = sum(1 for m in matches if m.get("outcome_for_current_home") == "home")
    draws = sum(1 for m in matches if m.get("outcome_for_current_home") == "draw")
    away_wins = sum(1 for m in matches if m.get("outcome_for_current_home") == "away")

    return {
        "played": len(matches),
        "home_wins": home_wins,
        "draws": draws,
        "away_wins": away_wins,
        "matches": matches,
        # Distinguishes "API returned zero H2H" from "fetch/summarize never succeeded".
        "fetched": True,
        # Bump when H2H fetch strategy changes so stale empty rows are refreshed.
        "source": get_settings().history_source_tag,
    }


def _line_token(label: str) -> str | None:
    parts = label.split()
    if len(parts) < 2:
        return None
    maybe = parts[-1]
    if any(ch.isdigit() for ch in maybe):
        return maybe
    return None


def _odd_float(odd: Any) -> float | None:
    try:
        value = float(odd)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _parse_line_market(
    bet_name: str,
    book_name: str,
    parsed_values: list[dict[str, Any]],
    *,
    home_labels: set[str],
    away_labels: set[str],
) -> dict[str, Any] | None:
    """Parse handicap / O-U lines; keep main line + multi-line board.

    Bookmakers return many lines. Main market = closest to even money.
    ``lines`` lists additional paired home/away quotes for UI (e.g. -0.5 and -1).
    """
    by_line: dict[str, dict[str, Any]] = {}
    for v in parsed_values:
        label = str(v.get("label") or "").strip()
        label_l = label.lower()
        odd = v.get("odd")
        line = _line_token(label)
        if not line:
            continue
        bucket = by_line.setdefault(line, {})
        # Match by first token / whole label — never substring "1" inside "-1".
        tokens = label_l.replace("/", " ").split()
        first = tokens[0] if tokens else ""
        if first in home_labels or label_l in home_labels or "home" in tokens or "over" in tokens:
            bucket["home"] = odd
        elif first in away_labels or label_l in away_labels or "away" in tokens or "under" in tokens:
            bucket["away"] = odd

    complete: list[tuple[float, str, Any, Any]] = []
    for line, sides in by_line.items():
        home_odd = sides.get("home")
        away_odd = sides.get("away")
        home_f = _odd_float(home_odd)
        away_f = _odd_float(away_odd)
        if home_f is None or away_f is None:
            continue
        score = abs(home_f - away_f)
        if line in {"2.5", "2,5"}:
            score -= 0.01
        complete.append((score, line, home_odd, away_odd))

    if not complete:
        return None

    complete.sort(key=lambda x: x[0])
    best_score, best_line, best_home, best_away = complete[0]

    def _abs_line(token: str) -> float:
        try:
            return abs(float(str(token).replace(",", ".")))
        except ValueError:
            return 99.0

    # Prefer common AH magnitudes for the multi-line board (-0.5, -1, 0, …).
    preferred = {0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0}
    board = sorted(complete, key=lambda x: (_abs_line(x[1]) not in preferred, _abs_line(x[1]), x[0]))
    lines_out: list[dict[str, Any]] = []
    seen_lines: set[str] = set()
    for _, line, home_odd, away_odd in board:
        if line in seen_lines:
            continue
        seen_lines.add(line)
        lines_out.append({"line": line, "home": home_odd, "away": away_odd})
        if len(lines_out) >= 6:
            break

    # Ensure main line is first in lines list.
    lines_out = [
        {"line": best_line, "home": best_home, "away": best_away},
        *[x for x in lines_out if x["line"] != best_line],
    ][:6]

    return {
        "bookmaker": book_name,
        "bet": bet_name,
        "line": best_line,
        "home": best_home,
        "away": best_away,
        "lines": lines_out,
        "values": parsed_values[:24],
    }


def parse_odds_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract 1X2 + Asian handicap + Goals O/U from first useful bookmaker."""
    bookmakers_out: list[dict[str, Any]] = []
    match_winner: dict[str, Any] | None = None
    asian_handicap: dict[str, Any] | None = None
    goals_ou: dict[str, Any] | None = None

    for item in extract_items(payload):
        bookmakers = item.get("bookmakers") or []
        for book in bookmakers:
            book_name = first_value(book, [["name"], ["bookmaker", "name"]], "unknown")
            bets = book.get("bets") or []
            for bet in bets:
                bet_label = first_value(bet, [["name"], ["label"]], "") or ""
                bet_name = str(bet_label).lower()
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
                    "bet": bet_label,
                    "values": parsed_values,
                }
                bookmakers_out.append(entry)

                if match_winner is None and (
                    "match winner" in bet_name
                    or bet_name in {"1x2", "winner", "full time result"}
                ):
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

                if asian_handicap is None and (
                    "asian handicap" in bet_name
                    or bet_name in {"handicap", "asian handi", "ah"}
                ):
                    asian_handicap = _parse_line_market(
                        bet_label,
                        book_name,
                        parsed_values,
                        home_labels={"home", "1"},
                        away_labels={"away", "2"},
                    )

                if goals_ou is None and (
                    "goals over/under" in bet_name
                    or "over/under" in bet_name
                    or bet_name in {"total goals", "totals", "ou"}
                ):
                    goals_ou = _parse_line_market(
                        bet_label,
                        book_name,
                        parsed_values,
                        home_labels={"over", "o"},
                        away_labels={"under", "u"},
                    )
            if match_winner and asian_handicap and goals_ou:
                break
        if match_winner and asian_handicap and goals_ou:
            break

    return {
        "match_winner": match_winner,
        "asian_handicap": asian_handicap,
        "goals_ou": goals_ou,
        "bookmakers": bookmakers_out[:8],
        "available": any(
            x is not None for x in (match_winner, asian_handicap, goals_ou)
        )
        or bool(bookmakers_out),
    }


def parse_standings_for_teams(
    payload: dict[str, Any],
    home_team_id: int,
    away_team_id: int,
    *,
    league_id: int | None = None,
    league_name: str | None = None,
) -> dict[str, Any]:
    """Extract home/away ranks from /standings payload (competition table)."""
    home_rank: int | None = None
    away_rank: int | None = None
    resolved_league_id = league_id
    resolved_league_name = league_name or ""
    group_name: str | None = None

    for item in extract_items(payload):
        league = item.get("league") if isinstance(item.get("league"), dict) else item
        if not isinstance(league, dict):
            continue
        if resolved_league_id is None:
            lid = first_value(league, [["id"]])
            if lid is not None:
                resolved_league_id = int(lid)
        if not resolved_league_name:
            resolved_league_name = str(first_value(league, [["name"]], "") or "")
        tables = league.get("standings") or item.get("standings") or []
        # API shape: standings = [[{rank,team,...}, ...]] or [[groupA],[groupB]]
        groups = tables if isinstance(tables, list) else []
        for group in groups:
            rows = group if isinstance(group, list) else [group]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                tid = first_value(row, [["team", "id"]])
                if tid is None:
                    continue
                tid_i = int(tid)
                rank = first_value(row, [["rank"], ["position"]])
                rank_i = int(rank) if rank is not None else None
                gname = first_value(row, [["group"], ["description"]])
                if tid_i == home_team_id and home_rank is None:
                    home_rank = rank_i
                    if gname:
                        group_name = str(gname)
                elif tid_i == away_team_id and away_rank is None:
                    away_rank = rank_i
                    if gname and group_name is None:
                        group_name = str(gname)

    return {
        "available": home_rank is not None or away_rank is not None,
        "league_id": resolved_league_id,
        "league_name": resolved_league_name,
        "group": group_name,
        "home_rank": home_rank,
        "away_rank": away_rank,
        # Competition table for this fixture's league (UECL/UCL/etc.), not domestic.
        "scope": "competition",
        "fetched": True,
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


_COMPARISON_LABELS = {
    "form": "近况",
    "att": "进攻",
    "def": "防守",
    "poisson_distribution": "泊松分布",
    "h2h": "交锋",
    "goals": "进球",
    "total": "综合",
}


def _side_percent(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_predictions_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize official GET /predictions into package.briefing (赛前简报).

    Not our local ML 「我的预测」. Empty coverage → available=False, fetched=True
    so detail refresh does not retry-storm.
    """
    items = extract_items(payload)
    if not items:
        return {"available": False, "fetched": True}

    item = items[0] if isinstance(items[0], dict) else {}
    pred = item.get("predictions") if isinstance(item.get("predictions"), dict) else {}
    winner_raw = pred.get("winner") if isinstance(pred.get("winner"), dict) else {}
    percent_raw = pred.get("percent") if isinstance(pred.get("percent"), dict) else {}
    goals_raw = pred.get("goals") if isinstance(pred.get("goals"), dict) else {}

    comparison_out: list[dict[str, Any]] = []
    comparison = item.get("comparison") if isinstance(item.get("comparison"), dict) else {}
    for key, sides in comparison.items():
        if not isinstance(sides, dict):
            continue
        comparison_out.append(
            {
                "key": key,
                "label": _COMPARISON_LABELS.get(str(key), str(key)),
                "home": _side_percent(sides.get("home")),
                "away": _side_percent(sides.get("away")),
            }
        )

    advice = first_value(pred, [["advice"]], None)
    winner_name = first_value(winner_raw, [["name"]], None)
    winner_comment = first_value(winner_raw, [["comment"]], None)
    under_over = first_value(pred, [["under_over"]], None)
    win_or_draw = pred.get("win_or_draw")
    percent = {
        "home": _side_percent(percent_raw.get("home")),
        "draw": _side_percent(percent_raw.get("draw")),
        "away": _side_percent(percent_raw.get("away")),
    }
    goals = {
        "home": _side_percent(goals_raw.get("home")),
        "away": _side_percent(goals_raw.get("away")),
    }

    available = bool(
        advice
        or winner_name
        or under_over
        or any(percent.values())
        or comparison_out
    )
    return {
        "available": available,
        "fetched": True,
        "advice": advice,
        "winner": {
            "id": first_value(winner_raw, [["id"]], None),
            "name": winner_name,
            "comment": winner_comment,
        },
        "win_or_draw": bool(win_or_draw) if win_or_draw is not None else None,
        "under_over": under_over,
        "goals": goals,
        "percent": percent,
        "comparison": comparison_out,
    }


def rehydrate_odds_markets(odds: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize odds; re-pick main AH / O-U lines from stored bookmaker values.

    Older rows may have stored the last exotic line (e.g. 4.5). Re-parsing from
    ``bookmakers`` values applies the balanced-line selection on every read.
    """
    if not isinstance(odds, dict):
        return {"available": False}
    books = odds.get("bookmakers") or []
    if not books:
        return odds

    synthetic = {
        "response": [
            {
                "bookmakers": [
                    {
                        "name": b.get("bookmaker"),
                        "bets": [
                            {
                                "name": b.get("bet"),
                                "values": [
                                    {"value": v.get("label"), "odd": v.get("odd")}
                                    for v in (b.get("values") or [])
                                ],
                            }
                        ],
                    }
                    for b in books
                    if isinstance(b, dict)
                ]
            }
        ]
    }
    parsed = parse_odds_payload(synthetic)
    merged = {**odds}
    if parsed.get("asian_handicap"):
        merged["asian_handicap"] = parsed["asian_handicap"]
    if parsed.get("goals_ou"):
        merged["goals_ou"] = parsed["goals_ou"]
    if merged.get("match_winner") is None and parsed.get("match_winner"):
        merged["match_winner"] = parsed["match_winner"]
    merged["available"] = bool(
        merged.get("match_winner")
        or merged.get("asian_handicap")
        or merged.get("goals_ou")
        or merged.get("bookmakers")
    )
    if odds.get("role") is not None:
        merged["role"] = odds.get("role")
    if odds.get("captured_at") is not None:
        merged["captured_at"] = odds.get("captured_at")
    return merged


def package_from_record(record: Any) -> dict[str, Any]:
    """Build API package dict from PreMatchData ORM row."""
    lineups = loads_json(getattr(record, "lineups_json", None), {})
    injuries = loads_json(getattr(record, "injuries_json", None), {})
    briefing = loads_json(getattr(record, "briefing_json", None), {})
    odds = rehydrate_odds_markets(
        loads_json(getattr(record, "odds_json", None), {"available": False})
    )
    odds_opening_raw = loads_json(
        getattr(record, "odds_opening_json", None), {"available": False}
    )
    odds_opening = (
        rehydrate_odds_markets(odds_opening_raw)
        if isinstance(odds_opening_raw, dict) and odds_opening_raw.get("available")
        else {"available": False}
    )
    return {
        "odds": odds,
        "odds_opening": odds_opening,
        "lineups": lineups if lineups else {"available": False, "home": None, "away": None},
        "injuries": injuries if injuries else {"available": False, "home": [], "away": []},
        "head_to_head": localize_matches_block(
            loads_json(getattr(record, "h2h_json", None), {"played": 0, "matches": []})
        ),
        "home_form": localize_matches_block(
            loads_json(getattr(record, "home_form_json", None), {"played": 0, "matches": []})
        ),
        "away_form": localize_matches_block(
            loads_json(getattr(record, "away_form_json", None), {"played": 0, "matches": []})
        ),
        "standings": loads_json(
            getattr(record, "standings_json", None),
            {"available": False},
        ),
        "briefing": briefing if briefing else {"available": False, "fetched": False},
        "home_formation": getattr(record, "home_formation", None)
        or (lineups.get("home") or {}).get("formation"),
        "away_formation": getattr(record, "away_formation", None)
        or (lineups.get("away") or {}).get("formation"),
    }
