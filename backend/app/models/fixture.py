from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    home_team_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    away_team_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    # Official short code when known: FT / AET / PEN / …
    status_short: Mapped[str | None] = mapped_column(String, nullable=True)
    # Regulation time (90') — used for prediction evaluation / ML labels.
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Extra time board (usually cumulative after ET); display only.
    et_home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    et_away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Penalty shootout; display only.
    pen_home: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pen_away: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

    league = relationship("League", backref="fixtures")
    home_team = relationship("Team", foreign_keys=[home_team_id], backref="home_fixtures")
    away_team = relationship("Team", foreign_keys=[away_team_id], backref="away_fixtures")

    def __repr__(self) -> str:
        return (
            f"<Fixture(id={self.id}, league_id={self.league_id}, "
            f"home_team_id={self.home_team_id}, away_team_id={self.away_team_id})>"
        )
