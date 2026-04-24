import base64
import json
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.core.config import get_settings

router = APIRouter(prefix="/images", tags=["images"])

AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4"]
SizeLabel = Literal["1K", "2K"]


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=5000)
    aspect_ratio: AspectRatio = "1:1"
    size_label: SizeLabel = "1K"
    model: str = "gpt-image-2"
    reference_images: list[str] = Field(default_factory=list, max_length=3)
    token_id: int


class GeneratedImage(BaseModel):
    b64_json: str
    mime_type: str = "image/png"
    revised_prompt: str | None = None


ASPECT_RATIO_SIZES: dict[str, dict[str, str]] = {
    "1K": {
        "1:1": "1024x1024",
        "16:9": "1792x1024",
        "9:16": "1024x1792",
        "4:3": "1536x1152",
        "3:4": "1152x1536",
    },
    "2K": {
        "1:1": "2048x2048",
        "16:9": "2816x1536",
        "9:16": "1536x2816",
        "4:3": "2304x1792",
        "3:4": "1792x2304",
    },
}




def unwrap_sub2api_response(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


async def resolve_openai_api_key(token_id: int, authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{settings.sub2api_base_url.rstrip('/')}/keys/{token_id}",
                headers={"Authorization": authorization},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Failed to load selected token") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail="Selected token is unavailable")

    token = unwrap_sub2api_response(response.json())
    if not isinstance(token, dict):
        raise HTTPException(status_code=502, detail="Invalid selected token response")

    group = token.get("group") if isinstance(token.get("group"), dict) else None
    if token.get("status") != "active" or not group or group.get("platform") != "openai":
        raise HTTPException(status_code=400, detail="Selected token is not an active OpenAI token")

    api_key = token.get("key")
    if not isinstance(api_key, str) or not api_key:
        raise HTTPException(status_code=400, detail="Selected token has no API key")

    return api_key

def extract_images(result: dict[str, Any]) -> list[GeneratedImage]:
    images: list[GeneratedImage] = []
    for item in result.get("data", []):
        b64_json = item.get("b64_json")
        if not b64_json:
            continue
        try:
            base64.b64decode(b64_json, validate=True)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Invalid image data returned") from exc
        images.append(
            GeneratedImage(
                b64_json=b64_json,
                revised_prompt=item.get("revised_prompt"),
            )
        )
    return images


def upstream_error(response: httpx.Response) -> HTTPException:
    try:
        detail: Any = response.json()
    except ValueError:
        detail = response.text
    return HTTPException(status_code=response.status_code, detail=detail)


@router.post("/generations")
async def generate_image(
    payload: ImageGenerationRequest,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    authorization: Annotated[str | None, Header()] = None,
):
    settings = get_settings()
    api_key = await resolve_openai_api_key(payload.token_id, authorization)

    size = ASPECT_RATIO_SIZES[payload.size_label][payload.aspect_ratio]
    upstream_payload: dict[str, Any] = {
        "model": payload.model,
        "prompt": payload.prompt,
        "size": size,
        "response_format": "b64_json",
        "n": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                settings.image_api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=upstream_payload,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Image generation timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Image service unavailable") from exc

    if response.status_code >= 400:
        raise upstream_error(response)

    return {
        "data": {
            "user_id": user.get("id"),
            "model": payload.model,
            "size": size,
            "images": [image.model_dump() for image in extract_images(response.json())],
        }
    }


@router.post("/edits")
async def edit_image(
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    prompt: Annotated[str, Form(min_length=1, max_length=5000)],
    aspect_ratio: Annotated[AspectRatio, Form()] = "1:1",
    size_label: Annotated[SizeLabel, Form()] = "1K",
    model: Annotated[str, Form()] = "gpt-image-2",
    reference_images: Annotated[list[UploadFile], File(max_length=3)] = [],
    token_id: Annotated[int, Form()] = 0,
    authorization: Annotated[str | None, Header()] = None,
):
    settings = get_settings()
    api_key = await resolve_openai_api_key(token_id, authorization)
    if not reference_images:
        raise HTTPException(status_code=400, detail="At least one reference image is required")
    if len(reference_images) > 3:
        raise HTTPException(status_code=400, detail="At most 3 reference images are allowed")

    size = ASPECT_RATIO_SIZES[size_label][aspect_ratio]
    data = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": "b64_json",
        "n": "1",
    }

    files: list[tuple[str, tuple[str, bytes, str]]] = []
    for image in reference_images:
        content = await image.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{image.filename} exceeds 5MB")
        content_type = image.content_type or "application/octet-stream"
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status_code=400, detail=f"Unsupported image type: {content_type}")
        files.append((settings.image_edit_field_name, (image.filename or "reference.png", content, content_type)))

    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                settings.image_edit_api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files=files,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Image edit timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Image service unavailable") from exc

    if response.status_code >= 400:
        # Some OpenAI-compatible gateways expect `image` repeated instead of `image[]`.
        if settings.image_edit_field_name != "image":
            fallback_files = [("image", file_tuple) for _, file_tuple in files]
            try:
                async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                    response = await client.post(
                        settings.image_edit_api_url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        data=data,
                        files=fallback_files,
                    )
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="Image service unavailable") from exc
        if response.status_code >= 400:
            raise upstream_error(response)

    return {
        "data": {
            "user_id": user.get("id"),
            "model": model,
            "size": size,
            "images": [image.model_dump() for image in extract_images(response.json())],
        }
    }
