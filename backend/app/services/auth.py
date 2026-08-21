"""Register / login / session verification and anonymous data claim."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bet_plan import BetPlan
from app.models.favorite_fixture import FAVORITE_SOURCE_AUTO, FavoriteFixture
from app.models.user import User
from app.models.user_session import UserSession
from app.services.user_scope import ANON_OWNER_ID, normalize_owner_id

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff]{2,32}$")
# Practical email check (local@domain); stored lowercased.
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
USERNAME_MAX_LEN = 128
SESSION_DAYS = 30
PBKDF2_ROUNDS = 120_000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str, *, salt: str | None = None) -> str:
    """Return ``salt$hex`` using PBKDF2-SHA256 (stdlib, no extra deps)."""
    salt_bytes = (salt or secrets.token_hex(16)).encode("utf-8")
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PBKDF2_ROUNDS,
    )
    return f"{salt_bytes.decode('utf-8')}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _hex = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt=salt), stored)


def normalize_account(username: str) -> str:
    """Strip; lowercase when the value looks like an email."""
    name = (username or "").strip()
    if "@" in name:
        return name.lower()
    return name


def validate_username(username: str) -> str:
    name = normalize_account(username)
    if not name or len(name) > USERNAME_MAX_LEN:
        raise ValueError(f"账号长度需 1–{USERNAME_MAX_LEN} 位")
    if EMAIL_RE.match(name) or USERNAME_RE.match(name):
        return name
    raise ValueError("账号需为邮箱，或 2–32 位字母/数字/下划线/中文")


def validate_password(password: str) -> str:
    if not password or len(password) < 6 or len(password) > 64:
        raise ValueError("密码长度需 6–64 位")
    return password


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    return (
        await db.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, user_id)


async def set_user_admin(
    db: AsyncSession, account: str, *, is_admin: bool = True
) -> User:
    """Promote / demote an existing account. Used by manage.py set-admin."""
    name = normalize_account(account)
    user = await get_user_by_username(db, name)
    if user is None:
        raise LookupError(f"账号不存在：{name}")
    user.is_admin = bool(is_admin)
    await db.flush()
    return user


async def register_user(db: AsyncSession, username: str, password: str) -> User:
    name = validate_username(username)
    pwd = validate_password(password)
    existing = await get_user_by_username(db, name)
    if existing is not None:
        raise LookupError("账号已被注册")
    user = User(
        id=str(uuid.uuid4()),
        username=name,
        password_hash=hash_password(pwd),
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    name = normalize_account(username)
    user = await get_user_by_username(db, name)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


async def create_session(db: AsyncSession, user_id: str) -> UserSession:
    token = secrets.token_urlsafe(32)
    row = UserSession(
        token=token,
        user_id=user_id,
        expires_at=_utc_now() + timedelta(days=SESSION_DAYS),
    )
    db.add(row)
    await db.flush()
    return row


async def revoke_session(db: AsyncSession, token: str) -> bool:
    row = await db.get(UserSession, token)
    if row is None:
        return False
    await db.delete(row)
    await db.flush()
    return True


async def resolve_user_id_from_token(
    db: AsyncSession, token: str | None
) -> str | None:
    if not token:
        return None
    row = await db.get(UserSession, token)
    if row is None:
        return None
    if row.expires_at < _utc_now():
        await db.delete(row)
        await db.flush()
        return None
    return row.user_id


async def claim_anonymous_private_data(
    db: AsyncSession, user_id: str
) -> dict[str, int]:
    """Move pre-auth bucket rows onto ``user_id`` once (manual favorites + plans).

    Shared ``source=auto`` picks stay in the anonymous bucket and are read
    through the separate auto-picks endpoint, never as user favorites.
    """
    owner = normalize_owner_id(user_id)
    claimed_favs = 0
    dropped_dup_favs = 0
    claimed_plans = 0

    owned_fixture_ids = {
        int(r[0])
        for r in (
            await db.execute(
                select(FavoriteFixture.fixture_id).where(
                    FavoriteFixture.user_id == owner
                )
            )
        ).all()
    }

    anon_favs = (
        await db.execute(
            select(FavoriteFixture).where(
                FavoriteFixture.user_id == ANON_OWNER_ID,
                FavoriteFixture.source != FAVORITE_SOURCE_AUTO,
            )
        )
    ).scalars().all()
    for fav in anon_favs:
        if int(fav.fixture_id) in owned_fixture_ids:
            await db.delete(fav)
            dropped_dup_favs += 1
            continue
        fav.user_id = owner
        owned_fixture_ids.add(int(fav.fixture_id))
        claimed_favs += 1

    result = await db.execute(
        update(BetPlan)
        .where(BetPlan.user_id == ANON_OWNER_ID)
        .values(user_id=owner)
    )
    claimed_plans = int(result.rowcount or 0)

    await db.flush()
    logger.info(
        "claim anonymous data user=%s favorites=%s dup_dropped=%s plans=%s",
        owner,
        claimed_favs,
        dropped_dup_favs,
        claimed_plans,
    )
    return {
        "favorites": claimed_favs,
        "favorites_dup_dropped": dropped_dup_favs,
        "plans": claimed_plans,
    }
