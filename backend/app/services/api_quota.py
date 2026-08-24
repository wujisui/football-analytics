"""Official API quota / free-plan guards for scheduled sync batches."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.config import get_settings

# API-Sports free tier typically allows fixtures only for a short sliding window
# ending at "today" (observed error: try from today-2 to today).
FREE_FIXTURES_LOOKBACK_DAYS = 2
FREE_FIXTURES_LOOKAHEAD_DAYS = 0
# Free /standings rejects current domestic seasons; clamp to this year.
FREE_STANDINGS_MAX_SEASON = 2024
# Cap unsubscribed 22:00 odds refresh so the day stays near the free allowance.
FREE_QUOTA_EVENING_ODDS_BUDGET = 40


def api_payload_errors(payload: dict[str, Any] | None) -> Any:
    if not isinstance(payload, dict):
        return None
    errors = payload.get("errors")
    if errors is None or errors == "" or errors == [] or errors == {}:
        return None
    return errors


def api_payload_unusable(payload: dict[str, Any] | None) -> bool:
    """True when the upstream body is an error shell (plan/rateLimit/etc.)."""
    return api_payload_errors(payload) is not None


def api_errors_text(errors: Any) -> str:
    return str(errors).lower() if errors is not None else ""


def api_errors_quota_exhausted(errors: Any) -> bool:
    """Daily request limit / rate limit — stop further official calls this batch."""
    text = api_errors_text(errors)
    if not text:
        return False
    return (
        "request limit" in text
        or "rate limit" in text
        or "ratelimit" in text
        or "too many requests" in text
    )


def api_errors_account_blocked(errors: Any) -> bool:
    """Account itself is suspended / disabled — every data endpoint is dead.

    API-Sports answers ``200`` with ``errors.access`` in this case, so a batch
    would otherwise "succeed" while saving nothing. Distinct from quota and plan
    limits: no failover or retry can help, only fixing the account.
    """
    text = api_errors_text(errors)
    if not text:
        return False
    return (
        "suspended" in text
        or "account is disabled" in text
        or "deactivated" in text
    )


def api_errors_plan_blocked(errors: Any) -> bool:
    """Plan does not allow this date/season/parameter."""
    text = api_errors_text(errors)
    if not text:
        return False
    return (
        "free plans do not have access" in text
        or ("plan" in text and "access" in text)
    )


def free_plan_fixture_date_bounds(today: date) -> tuple[date, date]:
    """Inclusive fixture ``date=`` window allowed on the free tier."""
    start = today - timedelta(days=FREE_FIXTURES_LOOKBACK_DAYS)
    end = today + timedelta(days=FREE_FIXTURES_LOOKAHEAD_DAYS)
    return start, end


def clip_fixture_dates_for_plan(
    days: list[date],
    today: date | None = None,
) -> list[date]:
    """Drop dates the current history mode cannot request officially.

    Paid (``API_HISTORY_MODE=full``) keeps the full list. Free mode clips to the
    observed free fixtures window so the batch does not burn quota on guaranteed
    ``plan`` errors.
    """
    if not days:
        return []
    settings = get_settings()
    if settings.uses_full_history:
        return list(days)
    base = today or date.today()
    start, end = free_plan_fixture_date_bounds(base)
    return sorted({d for d in days if start <= d <= end})
