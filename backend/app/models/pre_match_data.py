from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PreMatchData(Base):
    __tablename__ = "pre_match_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    home_formation: Mapped[str | None] = mapped_column(String, nullable=True)
    away_formation: Mapped[str | None] = mapped_column(String, nullable=True)
    injuries_home: Mapped[str | None] = mapped_column(Text, nullable=True)
    injuries_away: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather: Mapped[str | None] = mapped_column(String, nullable=True)
    home_win_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    draw_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_win_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Frozen prediction snapshot at last pre-match analysis (for results audit).
    recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    score_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    goal_lean: Mapped[str | None] = mapped_column(String, nullable=True)
    both_score_lean: Mapped[str | None] = mapped_column(String, nullable=True)
    handicap_lean: Mapped[str | None] = mapped_column(String, nullable=True)
    # Unified all-match reference.  Unlike daily picks this exists for every
    # fixture and never carries a star rating.
    reference_market: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reference_lean: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 含庄家抽水，仅供审计展示，不参与排序。
    reference_ev: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "market" | "model"：这条参考的概率来自盘口去水还是已过门禁的模型。
    reference_source: Mapped[str | None] = mapped_column(String(8), nullable=True)
    reference_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_alignment: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reference_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Structured pre-match package (JSON text)
    odds_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # First available pre-kickoff board (initial); immutable anchor.
    odds_opening_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Kickoff-relative boards: closest captures to T-6h (mid) and T-1h (late).
    odds_mid_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    odds_late_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    lineups_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    injuries_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    h2h_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    home_form_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    away_form_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    standings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Official API-Sports /predictions (赛前简报); not our local 1X2 model.
    briefing_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
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

    fixture = relationship("Fixture", backref="pre_match_data")

    def __repr__(self) -> str:
        return f"<PreMatchData(id={self.id}, fixture_id={self.fixture_id})>"
