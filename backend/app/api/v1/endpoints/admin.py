from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.tasks.scheduler import get_task_status, trigger_task

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Admin API is not configured. Set ADMIN_API_KEY in .env.",
        )
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin API key.")


class TriggerTaskRequest(BaseModel):
    name: str = Field(
        ...,
        description="任务名称：midday_fixtures_sync / pre_match_update / capture_results / clean_old_data / train_model",
    )


@router.get("/tasks")
async def list_task_status(_: None = Depends(verify_admin_key)) -> dict:
    return get_task_status()


@router.post("/tasks/trigger")
async def trigger_task_endpoint(
    body: TriggerTaskRequest,
    _: None = Depends(verify_admin_key),
) -> dict:
    try:
        await trigger_task(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "ok",
        "message": f"Task '{body.name}' triggered successfully.",
        "task_status": get_task_status(),
    }
