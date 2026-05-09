"""sub2api ops error webhook 接收端点"""
import asyncio
import hashlib
import hmac
import json
import logging
import time
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.core.config import get_settings
from app.webhooks.notifier import notify_user
from app.webhooks.rules import judge_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# 5 分钟去重：key=(user_id, error_type_fingerprint) -> last_sent_ts
_rate_limit: dict[tuple, float] = defaultdict(float)
_RATE_LIMIT_SECONDS = 300
_TIMESTAMP_SKEW_SECONDS = 300  # 允许的签名时间戳偏差
_lock = asyncio.Lock()


def _verify_signature(secret: str, timestamp: str, signature: str, body: bytes) -> bool:
    # 拒绝时间戳偏差超过 5 分钟的请求，防止重放攻击
    try:
        ts_int = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts_int) > _TIMESTAMP_SKEW_SECONDS:
        return False
    payload = timestamp.encode() + b"." + body
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def _dedup_key(user_id: int | None, error: dict) -> tuple:
    """去重 key：同一用户 + 同类错误 5 分钟内只发一次"""
    return (
        user_id,
        error.get("phase"),
        error.get("type"),
        error.get("status_code"),
        # 取 message 前 50 字作为指纹，区分不同路由错误原因
        (error.get("message") or "")[:50],
    )


async def _is_rate_limited(key: tuple) -> bool:
    """检查是否在去重窗口内（不写入）"""
    async with _lock:
        return time.monotonic() - _rate_limit[key] < _RATE_LIMIT_SECONDS


async def _mark_sent(key: tuple) -> None:
    """通知成功后写入去重时间戳"""
    async with _lock:
        _rate_limit[key] = time.monotonic()


async def _process_event(payload: dict) -> None:
    if payload.get("event") != "error":
        return

    error = payload.get("error", {})
    user_id: int | None = error.get("user_id")
    if not user_id:
        logger.debug("错误事件无 user_id，跳过通知")
        return

    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY 未配置，跳过 LLM 判断")
        return
    if not settings.lark_app_id or not settings.lark_app_secret:
        logger.warning("LARK_APP_ID/LARK_APP_SECRET 未配置，跳过飞书通知")
        return

    key = _dedup_key(user_id, error)
    if await _is_rate_limited(key):
        logger.debug("去重命中，跳过通知 user_id=%d key=%s", user_id, key)
        return

    should_notify, message = await judge_error(
        payload,
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url,
    )
    if not should_notify or not message:
        logger.debug("LLM 判断无需通知 user_id=%d", user_id)
        return

    sent = await notify_user(
        app_id=settings.lark_app_id,
        app_secret=settings.lark_app_secret,
        sub2api_base_url=settings.sub2api_base_url,
        admin_api_key=settings.sub2api_admin_api_key,
        user_id=user_id,
        message=message,
    )
    # 只有通知实际发出后才写入去重记录，避免 LLM/飞书偶发失败导致 5 分钟内静默
    if sent:
        await _mark_sent(key)


@router.post("/ops-errors", status_code=status.HTTP_200_OK)
async def receive_ops_error(request: Request, background_tasks: BackgroundTasks):
    """接收 sub2api ops error webhook 推送"""
    body = await request.body()
    settings = get_settings()

    if settings.ops_webhook_secret:
        ts = request.headers.get("X-Sub2Api-Timestamp", "")
        sig = request.headers.get("X-Sub2Api-Signature", "")
        if not ts or not sig:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少签名 Header")
        if not _verify_signature(settings.ops_webhook_secret, ts, sig, body):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="签名验证失败")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效 JSON")

    # 立即返回 200，异步处理
    background_tasks.add_task(_process_event, payload)
    return {"ok": True}
