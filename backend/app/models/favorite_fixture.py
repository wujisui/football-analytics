from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
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

    Composite PK ``(user_id, fixture_id)``. Guest / system auto tips use
    ``user_id=""`` (anonymous owner bucket).
    """

    __tablename__ = "favorite_fixtures"

    user_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default="",
        server_default="",
    )
    fixture_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=FAVORITE_SOURCE_MANUAL,
        server_default=FAVORITE_SOURCE_MANUAL,
    )
    # Populated only when source=auto: which single-lean market won ranking.
    auto_market: Mapped[str | None] = mapped_column(String(16), nullable=True)
    auto_lean: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Auto tip quality as 0.5–5 星（同一比赛日的入选场次内部排名）。
    quality_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<FavoriteFixture(user_id={self.user_id!r}, "
            f"fixture_id={self.fixture_id}, source={self.source!r}, "
            f"auto_market={self.auto_market!r})>"
        )
