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
