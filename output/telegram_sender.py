"""Telegram sender — sends messages with auto-splitting."""

import asyncio
import logging
from typing import Optional

import aiohttp

from config.loader import get_env, get_sources

logger = logging.getLogger(__name__)


class TelegramSender:
    """Sends messages to Telegram with automatic splitting for long content."""

    def __init__(self):
        self.bot_token = get_env("TELEGRAM_BOT_TOKEN")
        self.chat_id = get_env("TELEGRAM_CHAT_ID")
        if not self.bot_token or self.bot_token == "your_telegram_bot_token_here":
            logger.warning("TELEGRAM_BOT_TOKEN not configured — Telegram sending disabled")
            self.bot_token = None
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.max_length = 4096
        self._session = None

    async def send(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send message, auto-splitting if needed."""
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram credentials not configured")
            return False

        chunks = self._split_message(text)
        success = True

        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                chunk = f"[{i+1}/{len(chunks)}]\n{chunk}"

            result = await self._send_single(chunk, parse_mode)
            if not result:
                success = False
                logger.error(f"Failed to send chunk {i+1}/{len(chunks)}")

            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)  # rate limit

        return success

    async def send_document(self, file_path: str, caption: str = "") -> bool:
        """Send a file as document."""
        if not self.bot_token or not self.chat_id:
            return False

        url = f"{self.base_url}/sendDocument"
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field("chat_id", self.chat_id)
                    data.add_field("document", f, filename=file_path.split("/")[-1])
                    if caption:
                        data.add_field("caption", caption[:1024])
                    async with session.post(url, data=data) as resp:
                        return resp.status == 200
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            return False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a reusable aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _send_single(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a single message."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"Telegram API error {resp.status}: {body}")
                return resp.status == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def _split_message(self, text: str) -> list[str]:
        """Split message into chunks <= max_length, preferring newline boundaries."""
        if len(text) <= self.max_length:
            return [text]

        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > self.max_length:
                if current:
                    chunks.append(current.strip())
                current = line
            else:
                current = f"{current}\n{line}" if current else line

        if current:
            chunks.append(current.strip())

        return chunks

    def send_sync(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Synchronous wrapper for send()."""
        return asyncio.run(self.send(text, parse_mode))
