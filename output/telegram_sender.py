"""Telegram sender — sends messages with auto-splitting."""

import asyncio
import logging
from pathlib import Path


import aiohttp

from config.loader import get_env

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
        self._timeout = aiohttp.ClientTimeout(total=30)

    async def send(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send message, auto-splitting if needed."""
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram credentials not configured")
            return False

        chunks = self._split_message(text, reserve=20 if len(text) > self.max_length else 0)
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
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                with open(file_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field("chat_id", self.chat_id)
                    data.add_field("document", f, filename=Path(file_path).name)
                    if caption:
                        data.add_field("caption", caption[:1024])
                    async with session.post(url, data=data) as resp:
                        return resp.status == 200
        except (FileNotFoundError, PermissionError) as e:
            logger.error(f"Document file error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            return False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create a reusable aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _send_single(self, text: str, parse_mode: str = "Markdown", max_retries: int = 3) -> bool:
        """Send a single message with exponential backoff retry."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        for attempt in range(max_retries):
            try:
                session = await self._get_session()
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        return True
                    body = await resp.text()
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After", "5")
                        try:
                            wait = int(retry_after)
                        except ValueError:
                            wait = 5
                        logger.warning(f"Telegram rate limit (429), retrying after {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    if 500 <= resp.status < 600:
                        wait = 2 ** attempt
                        logger.warning(f"Telegram server error {resp.status}, retrying after {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    logger.error(f"Telegram API error {resp.status}: {body}")
                    return False
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Telegram send attempt {attempt + 1}/{max_retries} failed: {e}, retrying after {wait}s")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Failed to send Telegram message after {max_retries} attempts: {e}")
                    return False
        return False

    def _split_message(self, text: str, reserve: int = 0) -> list[str]:
        """Split message into chunks <= max_length, preferring newline boundaries."""
        max_len = self.max_length - reserve
        if len(text) <= max_len:
            return [text]

        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(line) > max_len:
                # Flush current first
                if current:
                    chunks.append(current.strip())
                    current = ""
                # Hard-split the oversized line
                for i in range(0, len(line), max_len):
                    chunks.append(line[i:i + max_len])
                continue

            if len(current) + len(line) + 1 > max_len:
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
