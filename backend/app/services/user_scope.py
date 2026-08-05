"""Owner scoping for user-private tables (favorites, bet plans, …).

Pre-auth: all rows live under ``user_id IS NULL`` (one install = one bucket).
Post-auth: pass the real user id; existing NULL rows can be claimed once
during first login migration (see AUTH_VIP_QUOTA §4.3).
"""

from __future__ import annotations

from typing import Any


def owner_is(column: Any, user_id: str | None) -> Any:
    """SQL filter matching the current owner bucket."""
    if user_id is None:
        return column.is_(None)
    return column == user_id
