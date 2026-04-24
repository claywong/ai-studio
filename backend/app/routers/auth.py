from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(user: Annotated[dict[str, Any], Depends(get_current_user)]):
    return {"data": user}
