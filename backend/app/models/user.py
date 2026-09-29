"""Auth user accounts (local register / login)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.services.user_roles import ROLE_USER


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # system_admin | ops_admin | user | vip. Exactly one system_admin, via script.
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ROLE_USER,
        server_default=ROLE_USER,
    )
    # VIP-only personal default league filter. Null = never saved.
    league_default_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id!r}, username={self.username!r}, "
            f"role={self.role!r})>"
        )
