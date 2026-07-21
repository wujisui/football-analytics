"""Point-in-time feature rows for 1X2 probability training / inference."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MatchFeature(Base):
    """Normalized numeric features captured at pre-match analysis time.

    Survives ``clean_old_data`` deletion of ``pre_match_data`` so finished
    fixtures remain usable as training labels.
    """

    __tablename__ = "match_features"
    __table_args__ = (UniqueConstraint("fixture_id", "feature_version", name="uq_match_features_fixture_ver"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    # Compact JSON: ordered feature dict matching FEATURE_NAMES.
    features_json: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional label after kickoff: home | draw | away
    label: Mapped[str | None] = mapped_column(String(8), nullable=True)
    model_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    home_win_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    draw_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_win_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Asian handicap (让球穿盘) — M-AH
    ah_line: Mapped[float | None] = mapped_column(Float, nullable=True)
    ah_home_odd: Mapped[float | None] = mapped_column(Float, nullable=True)
    ah_away_odd: Mapped[float | None] = mapped_column(Float, nullable=True)
    ah_features_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ah_label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ah_cover_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    ah_model_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ah_feature_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    fixture = relationship("Fixture", backref="match_features")

    def __repr__(self) -> str:
        return f"<MatchFeature(fixture_id={self.fixture_id}, ver={self.feature_version})>"
