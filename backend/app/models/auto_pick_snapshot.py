"""Frozen daily auto-pick snapshots for accuracy learning."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AutoPickSnapshot(Base):
    """One catalog auto recommendation frozen at pick time.

    Survives favorite_fixtures auto-row replacement so finished picks remain
    auditable for the 「每日推荐」 accuracy track.
    """

    __tablename__ = "auto_pick_snapshots"
    __table_args__ = (
        UniqueConstraint("fixture_id", name="uq_auto_pick_snapshots_fixture"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    lean: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decimal_odd: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Final ranking score after incentives (quality threshold compares this).
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_low: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        nullable=False,
    )
    picked_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<AutoPickSnapshot(fixture_id={self.fixture_id}, "
            f"match_day={self.match_day!r}, market={self.market!r})>"
        )
