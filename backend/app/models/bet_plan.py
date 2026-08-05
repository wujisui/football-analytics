from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BetPlan(Base):
    """Saved calculator plan (user-private).

    ``user_id`` is NULL pre-auth (single-tenant). After login, write/read with
    the real user id; claim NULL rows once on first login if desired.
    """

    __tablename__ = "bet_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    plan_day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    fold: Mapped[str] = mapped_column(String(16), nullable=False)
    multiplier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    selections_json: Mapped[str] = mapped_column(Text, nullable=False)
    saved_at: Mapped[datetime] = mapped_column(
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

    def __repr__(self) -> str:
        return f"<BetPlan(id={self.id}, user_id={self.user_id!r}, name={self.name!r})>"
