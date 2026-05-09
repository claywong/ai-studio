"""飞书 Bot DM 通知：user_id -> 查邮箱 -> 换 open_id -> 发消息（使用飞书官方 SDK lark-oapi）"""
import json
import logging

import httpx
import lark_oapi as lark
from lark_oapi.api.contact.v3 import BatchGetIdUserRequest, BatchGetIdUserRequestBody
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

logger = logging.getLogger(__name__)


def _build_lark_client(app_id: str, app_secret: str) -> lark.Client:
    return lark.Client.builder().app_id(app_id).app_secret(app_secret).build()


async def _get_user_email(sub2api_base_url: str, admin_api_key: str, user_id: int) -> str | None:
    """通过 sub2api admin API 查询用户邮箱"""
    url = f"{sub2api_base_url.rstrip('/')}/admin/users/{user_id}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"x-api-key": admin_api_key})
            resp.raise_for_status()
            return resp.json().get("data", {}).get("email")
    except Exception as exc:
        logger.warning("查询用户 %d 邮箱失败: %s", user_id, exc)
        return None


async def _email_to_open_id(lark_client: lark.Client, email: str) -> str | None:
    """邮箱换飞书 open_id"""
    req = (
        BatchGetIdUserRequest.builder()
        .user_id_type("open_id")
        .request_body(
            BatchGetIdUserRequestBody.builder()
            .emails([email])
            .build()
        )
        .build()
    )
    resp = await lark_client.contact.v3.user.abatch_get_id(req)
    if not resp.success():
        logger.warning("邮箱转 open_id 失败 code=%s msg=%s", resp.code, resp.msg)
        return None
    user_list = (resp.data.user_list or []) if resp.data else []
    if not user_list:
        return None
    return user_list[0].user_id  # user_id_type=open_id 时此字段即 open_id


async def _send_dm(lark_client: lark.Client, open_id: str, text: str) -> None:
    """发送飞书文本 DM"""
    req = (
        CreateMessageRequest.builder()
        .receive_id_type("open_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(open_id)
            .msg_type("text")
            .content(json.dumps({"text": text}))
            .build()
        )
        .build()
    )
    resp = await lark_client.im.v1.message.acreate(req)
    if not resp.success():
        raise RuntimeError(f"发送飞书消息失败 code={resp.code} msg={resp.msg}")


async def notify_user(
    *,
    app_id: str,
    app_secret: str,
    sub2api_base_url: str,
    admin_api_key: str,
    user_id: int,
    message: str,
) -> bool:
    """完整流程：user_id -> 邮箱 -> open_id -> 发 DM。返回是否成功。"""
    try:
        email = await _get_user_email(sub2api_base_url, admin_api_key, user_id)
        if not email:
            logger.warning("用户 %d 无邮箱，跳过飞书通知", user_id)
            return False

        lark_client = _build_lark_client(app_id, app_secret)

        open_id = await _email_to_open_id(lark_client, email)
        if not open_id:
            logger.warning("用户邮箱 %s 未找到对应飞书账号", email)
            return False

        await _send_dm(lark_client, open_id, message)
        logger.info("飞书通知已发送 -> user_id=%d email=%s", user_id, email)
        return True
    except Exception as exc:
        logger.error("飞书通知失败 user_id=%d: %s", user_id, exc)
        return False
