"""Response cache headers for the local read APIs (single source of truth)."""

from fastapi import Response


def set_no_store_headers(response: Response, data_source: str = "database") -> None:
    """All list/detail payloads read live local DB rows and may change after a sync.

    Browser-cached copies made the UI look stale until a hard reload, so no
    endpoint here is allowed to advertise a positive ``max-age``.
    """
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Data-Source"] = data_source
