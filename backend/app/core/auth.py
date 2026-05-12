from typing import Annotated, Any

import httpx
from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import get_settings


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    cached_user = getattr(request.state, "user", None)
    if cached_user:
        return cached_user

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{settings.sub2api_base_url.rstrip('/')}/auth/me",
                headers={"Authorization": authorization},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to validate session",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    payload = response.json()
    user = payload.get("data")
    if not isinstance(user, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    request.state.user = user
    return user


async def require_admin(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


REPORTER_EMAILS: frozenset[str] = frozenset([
    "xiqiang@g7.com.cn",
    "liuyunyang@g7.com.cn",
    "wangzhong@g7.com.cn",
    "wanghao_cd@g7.com.cn",
    "denglei@g7.com.cn",
    "guijiabin@g7.com.cn",
])


async def require_admin_or_reporter(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    role = user.get("role")
    email = user.get("email", "")
    if role not in ("admin", "reporter") and email not in REPORTER_EMAILS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access required")
    return user
