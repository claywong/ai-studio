from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import require_admin
from app.core.config import get_settings

router = APIRouter(prefix="/admin/reports/channel-monitors", tags=["channel-monitors"])


async def _admin_get(path: str, params: dict | None = None) -> Any:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{settings.sub2api_base_url.rstrip('/')}/{path.lstrip('/')}",
                headers={"x-api-key": settings.sub2api_admin_api_key},
                params=params,
            )
        response.raise_for_status()
        return response.json().get("data")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("")
async def list_monitors(_: Annotated[dict, Depends(require_admin)]):
    data = await _admin_get("/admin/channel-monitors", {"page": 1, "page_size": 100})
    return data


@router.get("/{monitor_id}/history")
async def get_history(
    monitor_id: int,
    _: Annotated[dict, Depends(require_admin)],
    limit: int = Query(200, ge=1, le=500),
    model: str | None = Query(None),
):
    params: dict = {"limit": limit}
    if model:
        params["model"] = model
    data = await _admin_get(f"/admin/channel-monitors/{monitor_id}/history", params)
    return data
