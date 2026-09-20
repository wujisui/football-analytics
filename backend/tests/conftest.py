import pytest

from app.services.ah_market_structure import fallback_thresholds, reset_threshold_cache


@pytest.fixture(autouse=True)
def _fallback_ah_market_thresholds(monkeypatch):
    """Unit tests use the documented fallbacks, not a local artifact file."""
    reset_threshold_cache()
    monkeypatch.setattr(
        "app.services.ah_market_structure.load_thresholds",
        fallback_thresholds,
    )
    yield
    reset_threshold_cache()
