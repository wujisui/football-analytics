"""Auth: password hashing, sessions, anonymous claim, favorite ownership."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.bet_plan import BetPlan
from app.models.favorite_fixture import (
    FAVORITE_SOURCE_AUTO,
    FAVORITE_SOURCE_MANUAL,
    FavoriteFixture,
)
from app.models.user_session import UserSession
from app.services import auth as auth_service
from app.services.user_scope import ANON_OWNER_ID


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _session() -> tuple[AsyncSession, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory(), engine


def test_set_user_admin_flag() -> None:
    async def _run() -> None:
        db, engine = await _session()
        try:
            user = await auth_service.register_user(db, "ops@example.com", "secret12")
            await db.commit()
            assert not bool(user.is_admin)

            promoted = await auth_service.set_user_admin(db, "ops@example.com")
            await db.commit()
            assert bool(promoted.is_admin)

            demoted = await auth_service.set_user_admin(
                db, "OPS@example.com", is_admin=False
            )
            await db.commit()
            assert not bool(demoted.is_admin)
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())


def test_password_roundtrip() -> None:
    stored = auth_service.hash_password("secret12")
    assert auth_service.verify_password("secret12", stored)
    assert not auth_service.verify_password("wrong", stored)


def test_validate_username_allows_email() -> None:
    assert auth_service.validate_username("User@Example.COM") == "user@example.com"
    assert auth_service.validate_username("球迷甲") == "球迷甲"
    try:
        auth_service.validate_username("bad@@mail")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_claim_moves_manual_keeps_auto() -> None:
    async def _run() -> None:
        db, engine = await _session()
        try:
            db.add(
                FavoriteFixture(
                    user_id=ANON_OWNER_ID,
                    fixture_id=101,
                    source=FAVORITE_SOURCE_MANUAL,
                    saved_at=_utcnow(),
                )
            )
            db.add(
                FavoriteFixture(
                    user_id=ANON_OWNER_ID,
                    fixture_id=202,
                    source=FAVORITE_SOURCE_AUTO,
                    auto_market="1x2",
                    auto_lean="胜",
                    saved_at=_utcnow(),
                )
            )
            db.add(
                BetPlan(
                    id="plan-1",
                    user_id=ANON_OWNER_ID,
                    name="测",
                    plan_day="2026-08-14",
                    fold="single",
                    multiplier=1,
                    selections_json="[{}]",
                    saved_at=_utcnow(),
                    updated_at=_utcnow(),
                )
            )
            await db.commit()

            user = await auth_service.register_user(db, "alice", "secret12")
            claimed = await auth_service.claim_anonymous_private_data(db, user.id)
            await db.commit()

            assert claimed["favorites"] == 1
            assert claimed["plans"] == 1

            manual = await db.get(FavoriteFixture, (user.id, 101))
            assert manual is not None
            assert manual.source == FAVORITE_SOURCE_MANUAL

            auto = await db.get(FavoriteFixture, (ANON_OWNER_ID, 202))
            assert auto is not None
            assert auto.source == FAVORITE_SOURCE_AUTO

            plan = await db.get(BetPlan, "plan-1")
            assert plan is not None
            assert plan.user_id == user.id
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())


def test_session_resolve_and_expire() -> None:
    async def _run() -> None:
        db, engine = await _session()
        try:
            user = await auth_service.register_user(db, "bob", "secret12")
            session = await auth_service.create_session(db, user.id)
            await db.commit()

            assert (
                await auth_service.resolve_user_id_from_token(db, session.token)
                == user.id
            )

            row = await db.get(UserSession, session.token)
            assert row is not None
            row.expires_at = _utcnow() - timedelta(seconds=1)
            await db.commit()

            assert (
                await auth_service.resolve_user_id_from_token(db, session.token)
                is None
            )
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())


def test_login_uses_httponly_cookie_and_never_returns_token() -> None:
    async def _run() -> None:
        db, engine = await _session()
        try:
            await auth_service.register_user(db, "dave", "secret12")
            await db.commit()

            from fastapi import FastAPI
            from httpx import ASGITransport, AsyncClient

            from app.api.v1.endpoints import auth as auth_endpoints
            from app.core.database import get_db

            app = FastAPI()
            app.include_router(auth_endpoints.router, prefix="/api/v1")

            async def _override_db():
                yield db

            app.dependency_overrides[get_db] = _override_db

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                res = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "dave", "password": "secret12"},
                )
                assert res.status_code == 200
                assert "token" not in res.json()

                set_cookie = res.headers.get("set-cookie", "").lower()
                assert "fa_session=" in set_cookie
                assert "httponly" in set_cookie
                assert "samesite=lax" in set_cookie

                # The cookie alone authenticates follow-up requests.
                me = await client.get("/api/v1/auth/me")
                assert me.status_code == 200
                assert me.json()["username"] == "dave"

                assert (await client.post("/api/v1/auth/logout")).status_code == 204
                assert (await client.get("/api/v1/auth/me")).status_code == 401
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())


def test_private_writes_require_login() -> None:
    async def _run() -> None:
        db, engine = await _session()
        try:
            from fastapi import FastAPI
            from httpx import ASGITransport, AsyncClient

            from app.api.v1.endpoints import bet_plans as bet_plans_endpoints
            from app.api.v1.endpoints import favorites as favorites_endpoints
            from app.core.database import get_db

            app = FastAPI()
            app.include_router(favorites_endpoints.router, prefix="/api/v1")
            app.include_router(bet_plans_endpoints.router, prefix="/api/v1")

            async def _override_db():
                yield db

            app.dependency_overrides[get_db] = _override_db

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                fav = await client.post("/api/v1/favorites", json={"fixture_id": 1})
                assert fav.status_code == 401
                assert fav.json()["detail"] == "请先登录"

                plan = await client.post(
                    "/api/v1/bet-plans",
                    json={
                        "name": "测",
                        "plan_day": "2026-08-15",
                        "fold": "single",
                        "multiplier": 1,
                        "selections": [],
                    },
                )
                assert plan.status_code == 401

                listed = await client.get("/api/v1/bet-plans")
                assert listed.status_code == 401
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())


def test_manual_favorites_and_shared_auto_picks_are_separate() -> None:
    async def _run() -> None:
        db, engine = await _session()
        try:
            user = await auth_service.register_user(db, "cara", "secret12")
            db.add(
                FavoriteFixture(
                    user_id=user.id,
                    fixture_id=1,
                    source=FAVORITE_SOURCE_MANUAL,
                    saved_at=_utcnow(),
                )
            )
            db.add(
                FavoriteFixture(
                    user_id=ANON_OWNER_ID,
                    fixture_id=2,
                    source=FAVORITE_SOURCE_AUTO,
                    auto_market="ou",
                    auto_lean="小(2.5)",
                    saved_at=_utcnow(),
                )
            )
            db.add(
                FavoriteFixture(
                    user_id=ANON_OWNER_ID,
                    fixture_id=3,
                    source=FAVORITE_SOURCE_MANUAL,
                    saved_at=_utcnow(),
                )
            )
            await db.commit()

            owner = user.id
            manual_rows = (
                await db.execute(
                    select(FavoriteFixture).where(
                        FavoriteFixture.user_id == owner,
                        FavoriteFixture.source == FAVORITE_SOURCE_MANUAL,
                    )
                )
            ).scalars().all()
            auto_rows = (
                await db.execute(
                    select(FavoriteFixture).where(
                        FavoriteFixture.user_id == ANON_OWNER_ID,
                        FavoriteFixture.source == FAVORITE_SOURCE_AUTO,
                    )
                )
            ).scalars().all()
            assert {r.fixture_id for r in manual_rows} == {1}
            assert {r.fixture_id for r in auto_rows} == {2}
        finally:
            await db.close()
            await engine.dispose()

    asyncio.run(_run())
