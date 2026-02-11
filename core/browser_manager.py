"""
Shared Playwright Browser Manager

Provides a singleton Playwright instance to avoid the "Sync API inside asyncio loop"
error that occurs when multiple clients each call sync_playwright().start().
"""
from typing import Optional
from playwright.sync_api import sync_playwright, Playwright

import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Singleton manager for the Playwright instance.
    All browser-based clients should use BrowserManager.get_playwright()
    instead of calling sync_playwright().start() directly.
    """
    _playwright: Optional[Playwright] = None

    @classmethod
    def get_playwright(cls) -> Playwright:
        """Returns the shared Playwright instance, creating it if needed."""
        if cls._playwright is None:
            logger.info("Starting shared Playwright instance...")
            cls._playwright = sync_playwright().start()
        return cls._playwright

    @classmethod
    def stop(cls):
        """Stops the shared Playwright instance."""
        if cls._playwright:
            logger.info("Stopping shared Playwright instance...")
            cls._playwright.stop()
            cls._playwright = None
