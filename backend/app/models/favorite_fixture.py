from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# manual = 用户手动关注；auto = 算法定时精选
FAVORITE_SOURCE_MANUAL = "manual"
FAVORITE_SOURCE_AUTO = "auto"

# Auto pick market keys (must match auto_favorites scoring markets).
AUTO_MARKET_1X2 = "1x2"
AUTO_MARKET_AH = "ah"
AUTO_MARKET_OU = "ou"
AUTO_MARKET_BTTS = "btts"
AUTO_MARKET_SCORE = "score"


class FavoriteFixture(Base):
    """User-private favorite list.

    Pre-auth: ``user_id`` is NULL (single-tenant per install).
    Post-auth: set ``user_id``; PK will need to become ``(user_id, fixture_id)``
    or a surrogate id — see docs/AUTH_VIP_QUOTA.md §4.3.
    """

    __tablename__ = "favorite_fixtures"

    fixture_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Nullable owner hook — NULL = local single-tenant until login ships.
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=FAVORITE_SOURCE_MANUAL,
        server_default=FAVORITE_SOURCE_MANUAL,
    )
    # Populated only when source=auto: which single-lean market won ranking.
    auto_market: Mapped[str | None] = mapped_column(String(16), nullable=True)
    auto_lean: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Auto tip below quality threshold — FavoriteButton second-tier star.
    quality_low: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<FavoriteFixture(fixture_id={self.fixture_id}, "
            f"user_id={self.user_id!r}, source={self.source!r}, "
            f"auto_market={self.auto_market!r})>"
        )
