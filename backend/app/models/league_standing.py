from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LeagueStanding(Base):
    """Shared standings snapshot for one league + season (list ranks read this)."""

    __tablename__ = "league_standings"
    __table_args__ = (
        UniqueConstraint("league_id", "season", name="uq_league_standings_league_season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season: Mapped[str] = mapped_column(String, nullable=False)
    league_name: Mapped[str] = mapped_column(String, default="", nullable=False)
    # {"by_team_id": {"123": {"rank": 1, "group": "..."}}, "fetched": true}
    ranks_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<LeagueStanding(league_id={self.league_id}, season={self.season!r})>"
        )
