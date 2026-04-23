"""Base collector with retry logic, error handling, and health tracking."""

import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class SourceHealth:
    """Track health of a data source."""
    source_name: str
    status: str = "healthy"  # healthy, degraded, down
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    failures_24h: int = 0
    total_retries: int = 0
    last_error: Optional[str] = None

    def mark_success(self):
        self.status = "healthy"
        self.last_success = datetime.now(timezone.utc).isoformat()
        self.failures_24h = 0
        self.last_error = None

    def mark_failure(self, error: str):
        self.failures_24h += 1
        self.last_failure = datetime.now(timezone.utc).isoformat()
        self.last_error = error
        if self.failures_24h >= 5:
            self.status = "down"
        elif self.failures_24h >= 2:
            self.status = "degraded"

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "status": self.status,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "failures_24h": self.failures_24h,
            "total_retries": self.total_retries,
            "last_error": self.last_error,
        }


class BaseCollector(ABC):
    """Base class for all data collectors with retry and health tracking."""

    def __init__(self, name: str, max_retries: int = 3, backoff_base: int = 2):
        self.name = name
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.health = SourceHealth(source_name=name)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ChainMonitor/1.0",
            "Accept": "application/json",
        })

    def fetch_with_retry(self, url: str, params: dict = None, headers: dict = None) -> Optional[dict]:
        """Fetch URL with exponential backoff retry."""
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=30)
                resp.raise_for_status()
                self.health.mark_success()
                return resp.json()
            except requests.exceptions.RequestException as e:
                wait = self.backoff_base ** attempt
                self.health.total_retries += 1
                logger.warning(f"[{self.name}] Attempt {attempt+1}/{self.max_retries} failed: {e}. Waiting {wait}s")
                if attempt < self.max_retries - 1:
                    time.sleep(wait)
                else:
                    self.health.mark_failure(str(e))
                    logger.error(f"[{self.name}] All {self.max_retries} retries failed for {url}")
                    return None

    def fetch_text_with_retry(self, url: str, params: dict = None) -> Optional[str]:
        """Fetch URL as text with retry."""
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                self.health.mark_success()
                return resp.text
            except requests.exceptions.RequestException as e:
                wait = self.backoff_base ** attempt
                self.health.total_retries += 1
                logger.warning(f"[{self.name}] Attempt {attempt+1}/{self.max_retries} failed: {e}. Waiting {wait}s")
                if attempt < self.max_retries - 1:
                    time.sleep(wait)
                else:
                    self.health.mark_failure(str(e))
                    return None

    @abstractmethod
    def collect(self) -> list[dict]:
        """Collect data and return list of raw events."""
        pass

    def get_health(self) -> dict:
        return self.health.to_dict()
