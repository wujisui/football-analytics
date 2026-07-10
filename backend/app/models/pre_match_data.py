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
    # Structured pre-match package (JSON text)
    odds_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    lineups_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    injuries_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    h2h_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    home_form_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    away_form_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    standings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
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
