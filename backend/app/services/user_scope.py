"""Owner scoping for user-private tables (favorites, bet plans, …).

Anonymous / pre-auth bucket uses empty string ``ANON_OWNER_ID`` (not SQL NULL),
so SQLite composite unique keys work. See ``docs/AUTH_VIP_QUOTA.md`` §4.4.
"""

from __future__ import annotations

from typing import Any

# Empty string = local single-tenant / guest bucket (legacy NULL rows migrated).
ANON_OWNER_ID = ""


def normalize_owner_id(user_id: str | None) -> str:
    """Map ``None`` / blank → anonymous bucket key."""
    if user_id is None:
        return ANON_OWNER_ID
    return str(user_id).strip()


def owner_is(column: Any, user_id: str | None) -> Any:
    """SQL filter matching the current owner bucket."""
    return column == normalize_owner_id(user_id)
