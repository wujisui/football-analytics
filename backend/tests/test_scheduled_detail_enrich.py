"""Scheduled full-detail enrich helpers (no live official API calls)."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.scheduled_detail_enrich import (
    UNLIMITED_DETAIL_BUDGET,
    _is_quota_error,
    _quota_looks_exhausted,
    resolve_detail_enrich_limit,
)


def test_quota_error_detection() -> None:
    assert _is_quota_error(RuntimeError("request limit reached"))
    assert _is_quota_error(RuntimeError("Your plan does not allow this endpoint"))
    assert not _is_quota_error(RuntimeError("fixture not found"))


def test_quota_exhausted_reads_cache_remaining(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.scheduled_detail_enrich.get_cache_service",
        lambda: SimpleNamespace(last_api_remaining=0),
    )
    assert _quota_looks_exhausted() is True

    monkeypatch.setattr(
        "app.services.scheduled_detail_enrich.get_cache_service",
        lambda: SimpleNamespace(last_api_remaining=12),
    )
    assert _quota_looks_exhausted() is False


def test_resolve_detail_enrich_limit() -> None:
    assert resolve_detail_enrich_limit(None, 10) == 10
    assert resolve_detail_enrich_limit(3, 10) == 3
    assert resolve_detail_enrich_limit(UNLIMITED_DETAIL_BUDGET, 10) is None
    assert resolve_detail_enrich_limit(0, 10) == 0
