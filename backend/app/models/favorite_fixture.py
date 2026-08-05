from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FavoriteFixture(Base):
    """User-private favorite list.

    Pre-auth: ``user_id`` is NULL (single-tenant per install).
    Post-auth: set ``user_id``; PK will need to become ``(user_id, fixture_id)``
    or a surrogate id — see docs/AUTH_VIP_QUOTA.md §4.3.
    """

    __tablename__ = "favorite_fixtures"

    fixture_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Nullable owner hook — NULL = local single-tenant until login ships.
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<FavoriteFixture(fixture_id={self.fixture_id}, user_id={self.user_id!r})>"
