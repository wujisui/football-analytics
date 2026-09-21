"""Frozen per-market candidates for recommendation audit and calibration."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecommendationCandidateSnapshot(Base):
    """One direction candidate captured before kickoff.

    Every available direction is stored, not only the daily Top 4.  Prematch
    refreshes replace these rows; once a fixture starts they remain frozen and
    become the unbiased feedback set for probability calibration.
    """

    __tablename__ = "recommendation_candidate_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id",
            "market",
            "direction",
            name="uq_recommendation_candidate_fixture_market_direction",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    lean: Mapped[str] = mapped_column(String(64), nullable=False)
    line: Mapped[float | None] = mapped_column(Float, nullable=True)

    model_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_model_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrator_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calibrated_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    implied_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    decimal_odd: Mapped[float | None] = mapped_column(Float, nullable=True)

    # JSON object with win / half_win / push / half_loss / loss probabilities.
    settlement_distribution_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    direction_strength: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", server_default="none"
    )
    direction_alignment: Mapped[str] = mapped_column(
        String(24), nullable=False, default="unknown", server_default="unknown"
    )
    direction_penalty: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.01, server_default="0.01"
    )
    adjusted_ev: Mapped[float | None] = mapped_column(Float, nullable=True)

    chosen_as_reference: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    chosen_as_daily_pick: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    skip_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    settlement_result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    actual_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
