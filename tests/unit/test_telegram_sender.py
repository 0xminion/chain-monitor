"""Tests for TelegramSender."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from output.telegram_sender import TelegramSender


class TestSplitMessage:
    """Test message splitting logic."""

    def test_short_message_no_split(self):
        sender = TelegramSender()
        sender.bot_token = "test"
        chunks = sender._split_message("Short message")
        assert len(chunks) == 1
        assert chunks[0] == "Short message"

    def test_long_message_splits_on_newline(self):
        sender = TelegramSender()
        sender.bot_token = "test"
        lines = ["Line " + str(i) for i in range(500)]
        text = "\n".join(lines)
        chunks = sender._split_message(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= sender.max_length

    def test_reserve_space(self):
        sender = TelegramSender()
        sender.bot_token = "test"
        text = "A" * 4100
        chunks = sender._split_message(text, reserve=20)
        for chunk in chunks:
            assert len(chunk) <= sender.max_length - 20

    def test_single_line_exceeds_max(self):
        """A single line longer than max_length should still be handled."""
        sender = TelegramSender()
        sender.bot_token = "test"
        text = "A" * 5000
        chunks = sender._split_message(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= sender.max_length


class TestSendSingle:
    """Test _send_single retry and error handling."""

    @pytest.fixture
    def sender(self):
        s = TelegramSender()
        s.bot_token = "test_token"
        s.chat_id = "12345"
        s.base_url = "https://api.telegram.org/bottest_token"
        return s

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self, sender):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.text = AsyncMock(return_value="OK")
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value = mock_post_ctx
        sender._session = mock_session

        result = await sender._send_single("hello")
        assert result is True
        assert mock_session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_429(self, sender):
        mock_resp = MagicMock()
        mock_resp.status = 429
        mock_resp.headers = {"Retry-After": "1"}
        mock_resp.text = AsyncMock(return_value="Too Many Requests")
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value = mock_post_ctx
        sender._session = mock_session

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await sender._send_single("hello", max_retries=2)
            assert result is False
            assert mock_session.post.call_count == 2
            mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_retry_on_502(self, sender):
        mock_resp = MagicMock()
        mock_resp.status = 502
        mock_resp.headers = {}
        mock_resp.text = AsyncMock(return_value="Bad Gateway")
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value = mock_post_ctx
        sender._session = mock_session

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await sender._send_single("hello", max_retries=2)
            assert result is False
            assert mock_session.post.call_count == 2
            mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self, sender):
        mock_resp = MagicMock()
        mock_resp.status = 400
        mock_resp.headers = {}
        mock_resp.text = AsyncMock(return_value="Bad Request")
        mock_post_ctx = AsyncMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value = mock_post_ctx
        sender._session = mock_session

        result = await sender._send_single("hello")
        assert result is False
        assert mock_session.post.call_count == 1


class TestSendSync:
    """Test synchronous wrapper."""

    def test_send_sync_calls_async_send(self):
        sender = TelegramSender()
        sender.bot_token = "test_token"
        sender.chat_id = "12345"

        with patch.object(sender, "send", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            result = sender.send_sync("hello")
            assert result is True
            mock_send.assert_called_once_with("hello", "Markdown")
