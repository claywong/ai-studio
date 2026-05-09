"""tests for app.webhooks.notifier"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.webhooks.notifier import _get_user_email, notify_user


# ---------------------------------------------------------------------------
# _get_user_email
# ---------------------------------------------------------------------------
class TestGetUserEmail:
    @pytest.mark.asyncio
    async def test_returns_email_on_success(self, respx_mock=None):
        # Arrange
        import httpx
        from unittest.mock import patch, AsyncMock

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"data": {"email": "user@example.com"}}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # Act
            result = await _get_user_email("https://g7e6ai.com/api/v1", "admin-key", 88)

        # Assert
        assert result == "user@example.com"

    @pytest.mark.asyncio
    async def test_returns_none_when_http_error(self):
        # Arrange
        import httpx
        from unittest.mock import patch, AsyncMock

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # Act
            result = await _get_user_email("https://g7e6ai.com/api/v1", "admin-key", 88)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_email_field_missing(self):
        # Arrange
        from unittest.mock import patch, AsyncMock

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"data": {}}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # Act
            result = await _get_user_email("https://g7e6ai.com/api/v1", "admin-key", 99)

        # Assert
        assert result is None


# ---------------------------------------------------------------------------
# notify_user — 完整流程
# ---------------------------------------------------------------------------
class TestNotifyUser:
    def _mock_lark_client(self, open_id: str | None):
        """构建假的 lark.Client，控制 email->open_id 和 send_dm 行为"""
        # batch_get_id 响应
        user_item = MagicMock()
        user_item.user_id = open_id
        batch_resp = MagicMock()
        batch_resp.success.return_value = open_id is not None
        batch_resp.data = MagicMock(user_list=[user_item] if open_id else [])

        # create message 响应
        create_resp = MagicMock()
        create_resp.success.return_value = True

        lark_client = MagicMock()
        lark_client.contact.v3.user.abatch_get_id = AsyncMock(return_value=batch_resp)
        lark_client.im.v1.message.acreate = AsyncMock(return_value=create_resp)
        return lark_client

    @pytest.mark.asyncio
    async def test_full_flow_success(self, mocker):
        # Arrange
        mocker.patch(
            "app.webhooks.notifier._get_user_email",
            new=AsyncMock(return_value="user@example.com"),
        )
        lark_client = self._mock_lark_client("ou_abc123")
        mocker.patch("app.webhooks.notifier._build_lark_client", return_value=lark_client)

        # Act
        result = await notify_user(
            app_id="cli_x",
            app_secret="sec_x",
            sub2api_base_url="https://g7e6ai.com/api/v1",
            admin_api_key="admin-key",
            user_id=88,
            message="测试通知消息",
        )

        # Assert
        assert result is True
        lark_client.im.v1.message.acreate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_email_not_found(self, mocker):
        # Arrange
        mocker.patch(
            "app.webhooks.notifier._get_user_email",
            new=AsyncMock(return_value=None),
        )
        # Act
        result = await notify_user(
            app_id="cli_x",
            app_secret="sec_x",
            sub2api_base_url="https://g7e6ai.com/api/v1",
            admin_api_key="admin-key",
            user_id=88,
            message="测试消息",
        )
        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_open_id_not_found(self, mocker):
        # Arrange
        mocker.patch(
            "app.webhooks.notifier._get_user_email",
            new=AsyncMock(return_value="user@example.com"),
        )
        lark_client = self._mock_lark_client(open_id=None)
        mocker.patch("app.webhooks.notifier._build_lark_client", return_value=lark_client)
        # Act
        result = await notify_user(
            app_id="cli_x",
            app_secret="sec_x",
            sub2api_base_url="https://g7e6ai.com/api/v1",
            admin_api_key="admin-key",
            user_id=88,
            message="测试消息",
        )
        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_send_dm_fails(self, mocker):
        # Arrange
        mocker.patch(
            "app.webhooks.notifier._get_user_email",
            new=AsyncMock(return_value="user@example.com"),
        )
        lark_client = self._mock_lark_client("ou_abc123")
        # 让 acreate 抛异常
        lark_client.im.v1.message.acreate = AsyncMock(side_effect=RuntimeError("send failed"))
        mocker.patch("app.webhooks.notifier._build_lark_client", return_value=lark_client)
        # Act
        result = await notify_user(
            app_id="cli_x",
            app_secret="sec_x",
            sub2api_base_url="https://g7e6ai.com/api/v1",
            admin_api_key="admin-key",
            user_id=88,
            message="测试消息",
        )
        # Assert
        assert result is False
