from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.core.config import get_settings

router = APIRouter(prefix="/tokens", tags=["tokens"])


class CreateTokenRequest(BaseModel):
    name: str = "G7E6 AI Studio"
    group_id: int | None = None


def auth_headers(authorization: str | None) -> dict[str, str]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"Authorization": authorization}


def unwrap_sub2api_response(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def normalize_key(item: dict[str, Any]) -> dict[str, Any]:
    group = item.get("group") if isinstance(item.get("group"), dict) else None
    return {
        "id": item.get("id"),
        "name": item.get("name") or "未命名令牌",
        "key": item.get("key"),
        "status": item.get("status"),
        "group_id": item.get("group_id"),
        "group_name": group.get("name") if group else None,
        "platform": group.get("platform") if group else None,
        "created_at": item.get("created_at"),
        "last_used_at": item.get("last_used_at"),
    }


async def request_sub2api(method: str, path: str, authorization: str, **kwargs: Any) -> Any:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.request(
            method,
            f"{settings.sub2api_base_url.rstrip('/')}{path}",
            headers=auth_headers(authorization),
            **kwargs,
        )

    if response.status_code >= 400:
        try:
            detail: Any = response.json()
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


async def get_openai_groups(authorization: str) -> list[dict[str, Any]]:
    payload = await request_sub2api("GET", "/groups/available", authorization)
    groups = unwrap_sub2api_response(payload)
    if not isinstance(groups, list):
        return []
    return [
        group for group in groups
        if isinstance(group, dict)
        and group.get("platform") == "openai"
        and group.get("status") == "active"
    ]


@router.get("")
async def list_tokens(
    _: Annotated[dict[str, Any], Depends(get_current_user)],
    authorization: Annotated[str | None, Header()] = None,
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    keys_payload = await request_sub2api(
        "GET",
        "/keys",
        authorization,
        params={"page": 1, "page_size": 100, "status": "active"},
    )
    keys_data = unwrap_sub2api_response(keys_payload)
    items = keys_data.get("items", keys_data) if isinstance(keys_data, dict) else keys_data
    if not isinstance(items, list):
        items = []

    openai_keys = []
    for item in items:
        if not isinstance(item, dict):
            continue
        group = item.get("group") if isinstance(item.get("group"), dict) else None
        if group and group.get("platform") == "openai" and item.get("status") == "active":
            openai_keys.append(normalize_key(item))

    return {"data": openai_keys}


@router.get("/openai-groups")
async def list_openai_groups(
    _: Annotated[dict[str, Any], Depends(get_current_user)],
    authorization: Annotated[str | None, Header()] = None,
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"data": await get_openai_groups(authorization)}


@router.post("")
async def create_token(
    payload: CreateTokenRequest,
    _: Annotated[dict[str, Any], Depends(get_current_user)],
    authorization: Annotated[str | None, Header()] = None,
):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    group_id = payload.group_id
    if group_id is None:
        openai_groups = await get_openai_groups(authorization)
        if not openai_groups:
            raise HTTPException(status_code=400, detail="No active OpenAI group available")
        group_id = openai_groups[0].get("id")

    created_payload = await request_sub2api(
        "POST",
        "/keys",
        authorization,
        json={"name": payload.name.strip() or "G7E6 AI Studio", "group_id": group_id},
    )
    created = unwrap_sub2api_response(created_payload)
    if not isinstance(created, dict):
        raise HTTPException(status_code=502, detail="Invalid token response")

    group = created.get("group") if isinstance(created.get("group"), dict) else None
    if group and group.get("platform") != "openai":
        raise HTTPException(status_code=502, detail="Created token is not an OpenAI token")

    return {"data": normalize_key(created)}
