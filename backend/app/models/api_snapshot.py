from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApiSnapshot(Base):
    """Persisted API responses for local-first reads (quota saving)."""

    __tablename__ = "api_snapshots"

    cache_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"<ApiSnapshot(cache_key={self.cache_key!r}, expires_at={self.expires_at})>"
