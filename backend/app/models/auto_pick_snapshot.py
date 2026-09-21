"""Frozen daily auto-pick snapshots for accuracy learning."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
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
    # 与 lean 同源的自洽展示，冻结用于审计（分析器那套另存 pre_match_data）。
    handicap_lean: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Probability before the validated per-market calibration layer.
    raw_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Probability after calibration, equivalent-event convergence and market-risk shrink.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decimal_odd: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    adjusted_ev: Mapped[float | None] = mapped_column(Float, nullable=True)
    implied_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calibrator_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    direction_alignment: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # Final ranking score is the adjusted EV.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 1–5 星 absolute strength band mapped from adjusted EV.
    quality_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
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
