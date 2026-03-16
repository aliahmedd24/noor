"""BrowserService — Registry for per-session browser access.

Hackathon version: single shared BrowserManager + ScreenAnalyzer.
Production version would use per-session BrowserContext via Playwright.
"""

from __future__ import annotations

from src.browser.manager import BrowserManager
from src.vision.analyzer import ScreenAnalyzer


class BrowserService:
    """Registry for per-session browser access.

    Wraps BrowserManager and ScreenAnalyzer into a single injectable
    dependency for all tool modules.
    """

    def __init__(self) -> None:
        self._manager: BrowserManager | None = None
        self._analyzer: ScreenAnalyzer | None = None

    async def start(
        self,
        headless: bool = True,
        channel: str | None = None,
        cdp_endpoint: str | None = None,
    ) -> None:
        """Start browser and create screen analyzer.

        Args:
            headless: Run browser in headless mode.
            channel: System browser channel (e.g., 'msedge').
            cdp_endpoint: CDP endpoint URL for attaching to external browser.
        """
        self._manager = BrowserManager(headless=headless)
        # BrowserManager reads channel/cdp from env vars in start(),
        # but we also support explicit overrides via env vars set before start
        import os
        if channel:
            os.environ["NOOR_BROWSER_CHANNEL"] = channel
        if cdp_endpoint:
            os.environ["NOOR_CDP_ENDPOINT"] = cdp_endpoint

        await self._manager.start()
        self._analyzer = ScreenAnalyzer()

    async def stop(self) -> None:
        """Stop browser and release resources."""
        if self._manager:
            await self._manager.stop()
            self._manager = None
            self._analyzer = None

    @property
    def browser(self) -> BrowserManager:
        """Return the BrowserManager instance."""
        return self._manager

    @property
    def analyzer(self) -> ScreenAnalyzer:
        """Return the ScreenAnalyzer instance."""
        return self._analyzer

    @property
    def is_started(self) -> bool:
        """Return True if the browser is started and ready."""
        return self._manager is not None and self._manager.is_started


# Module-level singleton
_service: BrowserService | None = None


def get_browser_service() -> BrowserService | None:
    """Return the module-level BrowserService singleton."""
    return _service


def set_browser_service(service: BrowserService) -> None:
    """Set the module-level BrowserService singleton."""
    global _service
    _service = service
