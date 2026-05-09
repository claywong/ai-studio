"""tests for app.webhooks.router"""
import hashlib
import hmac
import json
import time

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

import app.webhooks.router as router_module
from app.webhooks.router import (
    _dedup_key,
    _is_rate_limited,
    _mark_sent,
    _rate_limit,
    _verify_signature,
)


# ---------------------------------------------------------------------------
# _verify_signature
# ---------------------------------------------------------------------------
class TestVerifySignature:
    def _make_sig(self, secret: str, ts: str, body: bytes) -> str:
        payload = ts.encode() + b"." + body
        return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    def _fresh_ts(self) -> str:
        return str(int(time.time()))

    def test_valid_signature_returns_true(self):
        # Arrange
        ts = self._fresh_ts()
        secret, body = "s3cr3t", b'{"event":"error"}'
        sig = self._make_sig(secret, ts, body)
        # Act & Assert
        assert _verify_signature(secret, ts, sig, body) is True

    def test_wrong_secret_returns_false(self):
        # Arrange
        ts, body = self._fresh_ts(), b'{"event":"error"}'
        sig = self._make_sig("correct", ts, body)
        # Act & Assert
        assert _verify_signature("wrong", ts, sig, body) is False

    def test_tampered_body_returns_false(self):
        # Arrange
        ts = self._fresh_ts()
        secret = "s3cr3t"
        sig = self._make_sig(secret, ts, b'{"event":"error"}')
        # Act & Assert
        assert _verify_signature(secret, ts, sig, b'{"event":"tampered"}') is False

    def test_stale_timestamp_returns_false(self):
        # Arrange：时间戳早于 5 分钟前
        secret, body = "s3cr3t", b'{"event":"error"}'
        stale_ts = str(int(time.time()) - 301)
        sig = self._make_sig(secret, stale_ts, body)
        # Act & Assert
        assert _verify_signature(secret, stale_ts, sig, body) is False

    def test_future_timestamp_beyond_skew_returns_false(self):
        # Arrange：时间戳超出未来 5 分钟
        secret, body = "s3cr3t", b'{"event":"error"}'
        future_ts = str(int(time.time()) + 301)
        sig = self._make_sig(secret, future_ts, body)
        # Act & Assert
        assert _verify_signature(secret, future_ts, sig, body) is False

    def test_non_integer_timestamp_returns_false(self):
        # Arrange
        secret, body = "s3cr3t", b'{"event":"error"}'
        sig = self._make_sig(secret, "not-a-number", body)
        # Act & Assert
        assert _verify_signature(secret, "not-a-number", sig, body) is False


# ---------------------------------------------------------------------------
# _dedup_key
# ---------------------------------------------------------------------------
class TestDedupKey:
    def test_key_contains_user_id_phase_type_status_message_prefix(self):
        # Arrange
        error = {
            "phase": "routing",
            "type": "api_error",
            "status_code": 503,
            "message": "No available accounts: no available accounts",
        }
        # Act
        key = _dedup_key(88, error)
        # Assert
        assert key[0] == 88
        assert key[1] == "routing"
        assert key[2] == "api_error"
        assert key[3] == 503
        assert key[4] == "No available accounts: no available accounts"

    def test_message_truncated_to_50_chars(self):
        # Arrange
        long_msg = "A" * 100
        error = {"phase": "routing", "type": "api_error", "status_code": 503, "message": long_msg}
        # Act
        key = _dedup_key(1, error)
        # Assert
        assert len(key[4]) == 50

    def test_none_message_uses_empty_string(self):
        # Arrange
        error = {"phase": "routing", "type": "api_error", "status_code": 503, "message": None}
        # Act
        key = _dedup_key(1, error)
        # Assert
        assert key[4] == ""

    def test_none_user_id_allowed(self):
        # Arrange
        error = {"phase": "auth", "type": "authentication_error", "status_code": 401}
        # Act
        key = _dedup_key(None, error)
        # Assert
        assert key[0] is None


# ---------------------------------------------------------------------------
# _is_rate_limited / _mark_sent
# ---------------------------------------------------------------------------
class TestRateLimit:
    @pytest.fixture(autouse=True)
    def clear_rate_limit(self):
        _rate_limit.clear()
        yield
        _rate_limit.clear()

    @pytest.mark.asyncio
    async def test_new_key_not_rate_limited(self):
        # Arrange
        key = (1, "routing", "api_error", 503, "msg")
        # Act & Assert
        assert await _is_rate_limited(key) is False

    @pytest.mark.asyncio
    async def test_after_mark_sent_is_rate_limited(self):
        # Arrange
        key = (1, "routing", "api_error", 503, "msg")
        await _mark_sent(key)
        # Act & Assert
        assert await _is_rate_limited(key) is True

    @pytest.mark.asyncio
    async def test_after_window_expires_not_rate_limited(self):
        # Arrange
        key = (1, "routing", "api_error", 503, "msg")
        await _mark_sent(key)
        _rate_limit[key] = time.monotonic() - 301  # 超过 300s 窗口
        # Act & Assert
        assert await _is_rate_limited(key) is False

    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        # Arrange
        key_a = (1, "routing", "api_error", 503, "msg")
        key_b = (2, "routing", "api_error", 503, "msg")
        await _mark_sent(key_a)
        # Act & Assert
        assert await _is_rate_limited(key_b) is False


# ---------------------------------------------------------------------------
# HTTP endpoint — receive_ops_error
# ---------------------------------------------------------------------------
def _make_app_with_settings(overrides: dict):
    """构建带指定配置的 FastAPI 测试客户端"""
    from unittest.mock import patch

    from fastapi import FastAPI

    from app.webhooks.router import router

    app = FastAPI()
    app.include_router(router)

    settings_patch = {
        "ops_webhook_secret": "",
        "anthropic_api_key": "sk-test",
        "anthropic_base_url": "https://api.anthropic.com",
        "lark_app_id": "cli_test",
        "lark_app_secret": "secret_test",
        "sub2api_base_url": "https://g7e6ai.com/api/v1",
        "sub2api_admin_api_key": "admin-key",
        **overrides,
    }

    class FakeSettings:
        def __getattr__(self, name):
            return settings_patch.get(name, "")

    with patch("app.webhooks.router.get_settings", return_value=FakeSettings()):
        client = TestClient(app, raise_server_exceptions=False)
        return client


class TestReceiveOpsErrorEndpoint:
    VALID_PAYLOAD = {
        "event": "error",
        "timestamp": "2026-05-09T14:23:01Z",
        "error": {
            "phase": "routing",
            "type": "api_error",
            "severity": "P1",
            "status_code": 503,
            "message": "No available accounts: no available accounts",
            "user_id": 88,
        },
    }

    def test_returns_200_ok_for_valid_payload(self, mocker):
        # Arrange
        mocker.patch("app.webhooks.router._process_event")
        client = _make_app_with_settings({})
        # Act
        resp = client.post("/webhooks/ops-errors", json=self.VALID_PAYLOAD)
        # Assert
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_returns_400_for_invalid_json(self, mocker):
        # Arrange
        mocker.patch("app.webhooks.router._process_event")
        client = _make_app_with_settings({})
        # Act
        resp = client.post(
            "/webhooks/ops-errors",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
        # Assert
        assert resp.status_code == 400

    def test_returns_401_when_secret_configured_and_headers_missing(self, mocker):
        # Arrange
        mocker.patch("app.webhooks.router._process_event")
        from unittest.mock import patch

        from fastapi import FastAPI

        from app.webhooks.router import router

        app = FastAPI()
        app.include_router(router)

        class FakeSettings:
            ops_webhook_secret = "real-secret"
            anthropic_api_key = "sk-test"
            anthropic_base_url = "https://api.anthropic.com"
            lark_app_id = "cli_test"
            lark_app_secret = "secret_test"
            sub2api_base_url = "https://g7e6ai.com/api/v1"
            sub2api_admin_api_key = "admin-key"

        with patch("app.webhooks.router.get_settings", return_value=FakeSettings()):
            client = TestClient(app, raise_server_exceptions=False)
            # Act
            resp = client.post("/webhooks/ops-errors", json=self.VALID_PAYLOAD)
        # Assert
        assert resp.status_code == 401

    def test_returns_401_for_invalid_signature(self, mocker):
        # Arrange
        mocker.patch("app.webhooks.router._process_event")
        from unittest.mock import patch

        from fastapi import FastAPI

        from app.webhooks.router import router

        app = FastAPI()
        app.include_router(router)

        class FakeSettings:
            ops_webhook_secret = "real-secret"
            anthropic_api_key = "sk-test"
            anthropic_base_url = ""
            lark_app_id = "cli_test"
            lark_app_secret = "secret_test"
            sub2api_base_url = "https://g7e6ai.com/api/v1"
            sub2api_admin_api_key = "admin-key"

        with patch("app.webhooks.router.get_settings", return_value=FakeSettings()):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post(
                "/webhooks/ops-errors",
                json=self.VALID_PAYLOAD,
                headers={
                    "X-Sub2Api-Timestamp": "1700000000",
                    "X-Sub2Api-Signature": "sha256=wrongsig",
                },
            )
        assert resp.status_code == 401
