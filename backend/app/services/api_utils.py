import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "TBD": "pending",
    "NS": "pending",
    "NOT_STARTED": "pending",
    "SCHEDULED": "pending",
    "1H": "live",
    "HT": "live",
    "2H": "live",
    "ET": "live",
    "BT": "live",
    "P": "live",
    "SUSP": "live",
    "INT": "live",
    "LIVE": "live",
    "INPLAY": "live",
    "FT": "finished",
    "AET": "finished",
    "PEN": "finished",
    "FINISHED": "finished",
    "FULLTIME": "finished",
    "PST": "postponed",
    "CANC": "cancelled",
    "ABD": "cancelled",
    "AWD": "finished",
    "WO": "finished",
}


def parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    normalized = str(date_str).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
    logger.warning("Unable to parse date: %s", date_str)
    return None


def safe_get(data: Any, keys: list[str], default: Any = None) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def first_value(data: Any, paths: list[list[str]], default: Any = None) -> Any:
    for path in paths:
        value = safe_get(data, path, default=None)
        if value is not None:
            return value
    return default


def extract_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("response", "data", "result", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def map_fixture_status(short_status: str | None) -> str:
    if not short_status:
        return "pending"
    normalized = str(short_status).upper()
    return STATUS_MAP.get(normalized, str(short_status).lower())


def _as_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_fixture_scores(item: dict[str, Any]) -> dict[str, Any]:
    """Split regulation (90') vs extra-time / penalty for storage & display.

    API-Sports conventions (verified against live payloads):
    - ``score.fulltime`` — end of 90 minutes (authoritative for prediction eval)
    - ``score.extratime`` — often **goals scored in ET only** (not cumulative)
    - ``goals.*`` — final match goals including ET, excluding pens
    - ``score.penalty`` — shootout only

    We store:
    - ``home_goals`` / ``away_goals`` = regulation (fulltime)
    - ``et_*`` = score **after** extra time (cumulative), for display 「加时后」
    """
    short = first_value(
        item,
        [["fixture", "status", "short"], ["status", "short"], ["status"]],
    )
    status_short = str(short).upper() if short is not None else None

    ft_home = _as_int_or_none(first_value(item, [["score", "fulltime", "home"]]))
    ft_away = _as_int_or_none(first_value(item, [["score", "fulltime", "away"]]))
    et_raw_h = _as_int_or_none(first_value(item, [["score", "extratime", "home"]]))
    et_raw_a = _as_int_or_none(first_value(item, [["score", "extratime", "away"]]))
    pen_home = _as_int_or_none(first_value(item, [["score", "penalty", "home"]]))
    pen_away = _as_int_or_none(first_value(item, [["score", "penalty", "away"]]))
    goals_home = _as_int_or_none(first_value(item, [["goals", "home"]]))
    goals_away = _as_int_or_none(first_value(item, [["goals", "away"]]))

    # Never prefer goals.* over fulltime — goals includes ET on AET matches.
    if ft_home is not None and ft_away is not None:
        home_goals, away_goals = ft_home, ft_away
    elif status_short in {"AET", "PEN", "ET"}:
        # Without fulltime we cannot safely use goals (likely includes ET).
        home_goals, away_goals = None, None
    else:
        home_goals, away_goals = goals_home, goals_away

    et_home: int | None = None
    et_away: int | None = None
    if status_short in {"AET", "PEN", "ET"} or (
        et_raw_h is not None and et_raw_a is not None
    ):
        if goals_home is not None and goals_away is not None:
            # goals after ET (excl. pens) — best cumulative board
            et_home, et_away = goals_home, goals_away
        elif (
            ft_home is not None
            and ft_away is not None
            and et_raw_h is not None
            and et_raw_a is not None
        ):
            # Treat extratime as period goals when goals.* missing
            et_home, et_away = ft_home + et_raw_h, ft_away + et_raw_a
        elif et_raw_h is not None and et_raw_a is not None:
            et_home, et_away = et_raw_h, et_raw_a

    if status_short == "FT":
        et_home = et_away = pen_home = pen_away = None

    return {
        "home_goals": home_goals,
        "away_goals": away_goals,
        "et_home_goals": et_home,
        "et_away_goals": et_away,
        "pen_home": pen_home,
        "pen_away": pen_away,
        "status_short": status_short,
    }


def parse_remaining_requests(response: httpx.Response) -> int | None:
    for header in (
        "X-RateLimit-Requests-Remaining",
        "x-ratelimit-requests-remaining",
    ):
        value = response.headers.get(header)
        if value is not None:
            try:
                return int(value)
            except ValueError:
                logger.warning("Unable to parse remaining requests header: %s", value)
    return None
