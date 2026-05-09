"""tests for app.webhooks.rules"""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.webhooks.rules import judge_error


def _make_payload(phase, error_type, status_code, message, user_id=88):
    return {
        "event": "error",
        "error": {
            "phase": phase,
            "type": error_type,
            "severity": "P1",
            "status_code": status_code,
            "message": message,
            "user_id": user_id,
        },
    }


def _mock_anthropic_response(should_notify: bool, message: str):
    """构造 Anthropic SDK 的假响应对象"""
    content_block = MagicMock()
    content_block.text = json.dumps({"should_notify": should_notify, "message": message})
    resp = MagicMock()
    resp.content = [content_block]
    return resp


class TestJudgeError:
    @pytest.mark.asyncio
    async def test_routing_503_unknown_model_should_notify(self, mocker):
        # Arrange
        payload = _make_payload(
            "routing", "api_error", 503,
            "No available accounts: no available accounts (model: claude-3-5-haiku-20241022)",
        )
        mock_create = AsyncMock(return_value=_mock_anthropic_response(
            True, "您使用的模型 ID 不受支持，请改用 claude-haiku-4-5"
        ))
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is True
        assert "claude" in message.lower() or "模型" in message

    @pytest.mark.asyncio
    async def test_routing_503_cc_client_should_notify(self, mocker):
        # Arrange
        payload = _make_payload(
            "routing", "api_error", 503,
            "No available accounts: this group only allows Claude Code clients",
        )
        mock_create = AsyncMock(return_value=_mock_anthropic_response(
            True, "该分组仅支持官方 Claude Code 客户端"
        ))
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is True
        assert message != ""

    @pytest.mark.asyncio
    async def test_400_invalid_request_should_notify_retry(self, mocker):
        # Arrange
        payload = _make_payload("upstream", "invalid_request_error", 400, "Bad request")
        mock_create = AsyncMock(return_value=_mock_anthropic_response(
            True, "请稍后重试，或使用 /export 后新开会话"
        ))
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is True

    @pytest.mark.asyncio
    async def test_400_prohibited_content_should_notify(self, mocker):
        # Arrange
        payload = _make_payload(
            "upstream", "invalid_request_error", 400,
            "Your request contains prohibited content",
        )
        mock_create = AsyncMock(return_value=_mock_anthropic_response(
            True, "您的请求包含敏感词，请检查内容后重试"
        ))
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is True
        assert message != ""

    @pytest.mark.asyncio
    async def test_502_upstream_error_should_not_notify(self, mocker):
        # Arrange
        payload = _make_payload(
            "upstream", "upstream_error", 502,
            "Upstream service temporarily unavailable",
        )
        mock_create = AsyncMock(return_value=_mock_anthropic_response(False, ""))
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is False

    @pytest.mark.asyncio
    async def test_auth_error_should_not_notify(self, mocker):
        # Arrange
        payload = _make_payload("auth", "authentication_error", 401, "Invalid API Key")
        mock_create = AsyncMock(return_value=_mock_anthropic_response(False, ""))
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is False

    @pytest.mark.asyncio
    async def test_billing_error_should_not_notify(self, mocker):
        # Arrange
        payload = _make_payload("request", "billing_error", 402, "Insufficient balance")
        mock_create = AsyncMock(return_value=_mock_anthropic_response(False, ""))
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is False

    @pytest.mark.asyncio
    async def test_llm_exception_returns_false(self, mocker):
        # Arrange
        payload = _make_payload("routing", "api_error", 503, "some error")
        mock_create = AsyncMock(side_effect=Exception("network error"))
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is False
        assert message == ""

    @pytest.mark.asyncio
    async def test_llm_invalid_json_returns_false(self, mocker):
        # Arrange
        payload = _make_payload("routing", "api_error", 503, "some error")
        content_block = MagicMock()
        content_block.text = "not json at all"
        resp = MagicMock()
        resp.content = [content_block]
        mock_create = AsyncMock(return_value=resp)
        mocker.patch("anthropic.AsyncAnthropic", return_value=MagicMock(
            messages=MagicMock(create=mock_create)
        ))
        # Act
        should_notify, message = await judge_error(payload, "sk-test", "https://api.anthropic.com")
        # Assert
        assert should_notify is False
