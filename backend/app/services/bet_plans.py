"""Saved calculator plans — scoped by optional user_id (NULL = pre-auth local)."""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bet_plan import BetPlan
from app.services.user_scope import normalize_owner_id, owner_is

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_id() -> str:
    return f"{secrets.token_hex(4)}-{secrets.token_hex(3)}"


def _loads_selections(raw: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def plan_to_dict(row: BetPlan) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "saved_at": row.saved_at,
        "plan_day": row.plan_day,
        "fold": row.fold,
        "multiplier": row.multiplier,
        "selections": _loads_selections(row.selections_json),
    }


async def list_plans(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    plan_day: str | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(BetPlan)
        .where(owner_is(BetPlan.user_id, user_id))
        .order_by(BetPlan.saved_at.desc())
    )
    if plan_day:
        if not DATE_RE.match(plan_day):
            raise ValueError("plan_day must be YYYY-MM-DD")
        stmt = stmt.where(BetPlan.plan_day == plan_day)
    rows = (await db.execute(stmt)).scalars().all()
    return [plan_to_dict(row) for row in rows]


async def get_plan(
    db: AsyncSession,
    plan_id: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(BetPlan).where(
                BetPlan.id == plan_id,
                owner_is(BetPlan.user_id, user_id),
            )
        )
    ).scalar_one_or_none()
    return plan_to_dict(row) if row else None


async def create_plan(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    name: str,
    plan_day: str,
    fold: str,
    multiplier: int,
    selections: list[dict[str, Any]],
    plan_id: str | None = None,
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("name required")
    if not DATE_RE.match(plan_day):
        raise ValueError("plan_day must be YYYY-MM-DD")
    if not isinstance(selections, list) or not selections:
        raise ValueError("selections required")
    mult = max(1, int(multiplier) or 1)
    now = _utc_now()
    row = BetPlan(
        id=(plan_id or _new_id())[:64],
        user_id=normalize_owner_id(user_id),
        name=name[:80],
        plan_day=plan_day,
        fold=str(fold)[:16],
        multiplier=mult,
        selections_json=json.dumps(selections, ensure_ascii=False),
        saved_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return plan_to_dict(row)


async def rename_plan(
    db: AsyncSession,
    plan_id: str,
    name: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    name = (name or "").strip()
    if not name:
        raise ValueError("name required")
    row = (
        await db.execute(
            select(BetPlan).where(
                BetPlan.id == plan_id,
                owner_is(BetPlan.user_id, user_id),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.name = name[:80]
    row.updated_at = _utc_now()
    await db.commit()
    await db.refresh(row)
    return plan_to_dict(row)


async def delete_plan(
    db: AsyncSession,
    plan_id: str,
    *,
    user_id: str | None = None,
) -> bool:
    row = (
        await db.execute(
            select(BetPlan).where(
                BetPlan.id == plan_id,
                owner_is(BetPlan.user_id, user_id),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True


async def plan_days(
    db: AsyncSession,
    *,
    user_id: str | None = None,
) -> list[str]:
    rows = (
        await db.execute(
            select(BetPlan.plan_day)
            .where(owner_is(BetPlan.user_id, user_id))
            .distinct()
        )
    ).all()
    return sorted({r[0] for r in rows if r[0]})
