"""用 Anthropic SDK 判断错误事件是否需要通知用户，以及通知内容。"""
import json
import logging

import anthropic

logger = logging.getLogger(__name__)

# 支持的 Claude 标准模型 ID
SUPPORTED_CLAUDE_MODELS = {
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
    "claude-opus-4-6",
    "claude-opus-4-7",
}

_SYSTEM_PROMPT = """\
你是一个 AI API 平台的错误处理专家。你的职责是分析错误事件，判断是否需要向用户发送通知，以及通知内容应该是什么。

平台规则如下：

【路由错误 503 规则】
1. 若 message 包含 "No available accounts" 且包含模型名称（如 "claude-3-5-haiku-20241022"），
   说明用户使用了不支持的模型 ID。
   - 支持的 Claude 标准模型 ID 有：claude-sonnet-4-6、claude-haiku-4-5、claude-opus-4-6、claude-opus-4-7
   - 国产模型（如 deepseek、qwen 等）也必须使用标准模型 ID
   - 需要告诉用户：当前模型 ID 不支持，请改用正确的标准模型 ID，并给出示例

2. 若 message 包含 "No available accounts: this group only allows Claude Code clients"，
   说明用户不是官方 Claude Code 客户端，或者版本过低。
   - 需要告知用户：该分组仅支持官方 Claude Code 客户端访问，请确认使用的是最新版官方客户端

3. 若 message 包含 "No available accounts: this group only allows" 且包含 "Claude（订阅）" 不支持的信息，
   说明当前分组不支持该模型。告知用户当前分组不支持该模型。

【400 错误规则】
- phase=upstream 或 type=invalid_request_error 的 400 错误：提醒用户重试，或使用 /export 后新开会话

- 若 message 包含 "Your request contains prohibited content"：说明请求中包含敏感词，请用户检查内容后重试

【502/504 错误规则】
- Upstream service temporarily unavailable 或 Upstream request failed 等上游错误：不通知用户

【不需要通知的情况】
- phase=auth（鉴权失败）：用户自己的问题，不通知
- phase=request 且是余额不足（billing_error）：用户自己余额问题，不通知
- severity=P2 或 P3 的普通 4xx：一般不通知，除非符合上述 400 规则

请根据以上规则分析错误，返回 JSON 格式（不要 markdown 代码块，直接 JSON）：
{
  "should_notify": true/false,
  "message": "要发给用户的消息（中文，简洁友好，不超过200字）"
}

若 should_notify=false，message 可为空字符串。
"""


async def judge_error(error_payload: dict, api_key: str, base_url: str) -> tuple[bool, str]:
    """
    使用 LLM 判断是否需要通知用户。
    返回 (should_notify, message)。
    """
    error = error_payload.get("error", {})
    error_summary = json.dumps(error, ensure_ascii=False, indent=2)

    client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
    try:
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"请分析以下错误事件：\n\n{error_summary}",
                }
            ],
        )
        raw = resp.content[0].text.strip()
        # 剥离模型偶尔返回的 markdown 代码块
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        return bool(result.get("should_notify")), result.get("message", "")
    except Exception as exc:
        logger.error("LLM 判断失败，跳过通知: %s", exc)
        return False, ""
