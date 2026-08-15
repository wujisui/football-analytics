from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_auth import RequiredUserId
from app.api.v1.http_cache import set_no_store_headers
from app.core.database import get_db
from app.schemas.response import (
    BetPlanCreateRequest,
    BetPlanDaysResponse,
    BetPlanRenameRequest,
    BetPlanResponse,
    BetPlansResponse,
)
from app.services import bet_plans as bet_plans_service

router = APIRouter(prefix="/bet-plans", tags=["bet-plans"])


@router.get("", response_model=BetPlansResponse)
async def list_bet_plans(
    response: Response,
    user_id: RequiredUserId,
    plan_day: str | None = Query(default=None, description="按赛程日过滤 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
) -> BetPlansResponse:
    set_no_store_headers(response)
    try:
        items = await bet_plans_service.list_plans(
            db, user_id=user_id, plan_day=plan_day
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BetPlansResponse(
        total=len(items),
        plans=[BetPlanResponse(**row) for row in items],
    )


@router.get("/days", response_model=BetPlanDaysResponse)
async def list_bet_plan_days(
    response: Response,
    user_id: RequiredUserId,
    db: AsyncSession = Depends(get_db),
) -> BetPlanDaysResponse:
    set_no_store_headers(response)
    days = await bet_plans_service.plan_days(db, user_id=user_id)
    return BetPlanDaysResponse(days=days)


@router.get("/{plan_id}", response_model=BetPlanResponse)
async def get_bet_plan(
    plan_id: str,
    response: Response,
    user_id: RequiredUserId,
    db: AsyncSession = Depends(get_db),
) -> BetPlanResponse:
    set_no_store_headers(response)
    row = await bet_plans_service.get_plan(db, plan_id, user_id=user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    return BetPlanResponse(**row)


@router.post("", response_model=BetPlanResponse)
async def create_bet_plan(
    body: BetPlanCreateRequest,
    response: Response,
    user_id: RequiredUserId,
    db: AsyncSession = Depends(get_db),
) -> BetPlanResponse:
    set_no_store_headers(response)
    try:
        row = await bet_plans_service.create_plan(
            db,
            user_id=user_id,
            name=body.name,
            plan_day=body.plan_day,
            fold=body.fold,
            multiplier=body.multiplier,
            selections=body.selections,
            plan_id=body.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BetPlanResponse(**row)


@router.patch("/{plan_id}", response_model=BetPlanResponse)
async def rename_bet_plan(
    plan_id: str,
    body: BetPlanRenameRequest,
    response: Response,
    user_id: RequiredUserId,
    db: AsyncSession = Depends(get_db),
) -> BetPlanResponse:
    set_no_store_headers(response)
    try:
        row = await bet_plans_service.rename_plan(
            db, plan_id, body.name, user_id=user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    return BetPlanResponse(**row)


@router.delete("/{plan_id}", status_code=204)
async def delete_bet_plan(
    plan_id: str,
    response: Response,
    user_id: RequiredUserId,
    db: AsyncSession = Depends(get_db),
) -> Response:
    set_no_store_headers(response)
    await bet_plans_service.delete_plan(db, plan_id, user_id=user_id)
    return Response(status_code=204)
