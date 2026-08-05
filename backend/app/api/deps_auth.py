"""Auth dependency stubs — real login will replace the body of these helpers.

Until then every request is treated as the pre-auth single-tenant owner
(``user_id is NULL``). See ``docs/AUTH_VIP_QUOTA.md`` §4.3.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends


async def get_current_user_id() -> str | None:
    """Return authenticated user id, or ``None`` for the local single-tenant bucket.

    Hook for JWT / session: parse Authorization / cookie here and return a
    stable string id. Do **not** invent anonymous per-browser ids — that would
    orphan rows when the real login lands.
    """
    return None


CurrentUserId = Annotated[str | None, Depends(get_current_user_id)]
