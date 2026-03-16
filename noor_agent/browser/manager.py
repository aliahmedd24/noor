"""BrowserManager — Multi-strategy Playwright browser lifecycle manager.

Launch Strategy Priority:
  1. CDP Connect   — if NOOR_CDP_ENDPOINT is set
  2. System Channel — if NOOR_BROWSER_CHANNEL is set (e.g., "msedge", "chrome")
  3. Bundled Chromium — (default) for Docker / Cloud Run / CI

Windows: Set NOOR_BROWSER_CHANNEL=msedge. Do NOT run `playwright install chromium`.
"""

from __future__ import annotations

import os

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

logger = structlog.get_logger(__name__)


class BrowserManager:
    """Manages a single Playwright browser session for Noor."""

    LAUNCH_ARGS: list[str] = [
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--disable-ipc-flooding-protection",
        "--disable-translate",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars",
    ]

    DEFAULT_VIEWPORT_WIDTH: int = 1280
    DEFAULT_VIEWPORT_HEIGHT: int = 800

    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
        viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
    ):
        """Initialize BrowserManager.

        Args:
            headless: Run browser in headless mode. Default: True.
            viewport_width: Browser viewport width in pixels. Default: 1280.
            viewport_height: Browser viewport height in pixels. Default: 800.
        """
        self._headless = headless
        self._viewport_width = viewport_width
        self._viewport_height = viewport_height
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._launch_strategy: str = "unknown"

    async def start(self) -> None:
        """Launch browser using the appropriate strategy.

        Strategy selection (in priority order):
        1. If NOOR_CDP_ENDPOINT env var is set -> connect via CDP
        2. If NOOR_BROWSER_CHANNEL env var is set -> launch system browser
        3. Otherwise -> launch bundled Playwright Chromium

        Raises:
            RuntimeError: If all launch strategies fail.
        """
        self._playwright = await async_playwright().start()

        cdp_endpoint = os.getenv("NOOR_CDP_ENDPOINT")
        channel = os.getenv("NOOR_BROWSER_CHANNEL")

        if cdp_endpoint:
            await self._start_cdp(cdp_endpoint)
        elif channel:
            await self._start_channel(channel)
        else:
            await self._start_bundled()

        if not self._context:
            self._context = await self._browser.new_context(
                viewport={
                    "width": self._viewport_width,
                    "height": self._viewport_height,
                },
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            self._context.set_default_timeout(15000)
            self._page = await self._context.new_page()

        logger.info(
            "browser_started",
            strategy=self._launch_strategy,
            viewport=f"{self._viewport_width}x{self._viewport_height}",
        )

    async def _start_cdp(self, endpoint: str) -> None:
        """Strategy 1: Connect to an externally-managed browser via CDP."""
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(endpoint)
            self._launch_strategy = "cdp"
            if self._browser.contexts:
                self._context = self._browser.contexts[0]
                if self._context.pages:
                    self._page = self._context.pages[0]
            logger.info("browser_cdp_connected", endpoint=endpoint)
        except Exception as e:
            logger.warning("browser_cdp_failed", endpoint=endpoint, error=str(e))
            channel = os.getenv("NOOR_BROWSER_CHANNEL")
            if channel:
                await self._start_channel(channel)
            else:
                await self._start_bundled()

    async def _start_channel(self, channel: str) -> None:
        """Strategy 2: Launch a system-installed browser (Edge, Chrome).

        Args:
            channel: Browser channel name ("msedge", "chrome", etc.).
        """
        try:
            self._browser = await self._playwright.chromium.launch(
                channel=channel,
                headless=self._headless,
                args=self.LAUNCH_ARGS,
            )
            self._launch_strategy = f"channel:{channel}"
            logger.info("browser_channel_launched", channel=channel)
        except Exception as e:
            logger.warning(
                "browser_channel_failed", channel=channel, error=str(e)
            )
            await self._start_bundled()

    async def _start_bundled(self) -> None:
        """Strategy 3: Launch Playwright's bundled Chromium."""
        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                args=self.LAUNCH_ARGS,
            )
            self._launch_strategy = "bundled_chromium"
            logger.info("browser_bundled_launched")
        except Exception as e:
            raise RuntimeError(
                f"All browser launch strategies failed. Last error: {e}\n\n"
                f"TROUBLESHOOTING:\n"
                f"  Windows: Set NOOR_BROWSER_CHANNEL=msedge in your .env file.\n"
                f"           Do NOT run 'playwright install chromium' on Windows.\n"
                f"  Docker:  Ensure 'playwright install chromium' is in Dockerfile.\n"
                f"  CDP:     Launch Edge manually with:\n"
                f"           msedge --remote-debugging-port=9222 --headless "
                f"--disable-gpu\n"
                f"           Then set NOOR_CDP_ENDPOINT=http://localhost:9222"
            ) from e

    async def stop(self) -> None:
        """Close browser and clean up all resources."""
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser and self._launch_strategy != "cdp":
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning("browser_cleanup_error", error=str(e))
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None

    async def get_page(self) -> Page:
        """Return the active Playwright Page object.

        Returns:
            The active Page instance.

        Raises:
            RuntimeError: If browser has not been started.
        """
        if not self._page or self._page.is_closed():
            raise RuntimeError(
                "Browser not started or page is closed. Call start() first."
            )
        return self._page

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict:
        """Navigate to a URL and wait for the page to load.

        Args:
            url: The URL to navigate to. Must include protocol (https://).
            wait_until: Playwright wait condition. Default: 'domcontentloaded'.

        Returns:
            dict with keys: success, url, title, error.
        """
        try:
            page = await self.get_page()
            await page.goto(url, wait_until=wait_until)
            return {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "error": None,
            }
        except Exception as e:
            logger.error("navigation_failed", url=url, error=str(e))
            return {
                "success": False,
                "url": url,
                "title": "",
                "error": f"Navigation failed: {str(e)}",
            }

    async def take_screenshot(
        self, full_page: bool = False, quality: int = 80
    ) -> bytes:
        """Capture a screenshot of the current viewport.

        Args:
            full_page: If True, capture the entire scrollable page. Default: False.
            quality: JPEG quality 1-100. Default: 80.

        Returns:
            JPEG image bytes. Empty bytes on failure.
        """
        try:
            page = await self.get_page()
            return await page.screenshot(
                type="jpeg",
                quality=quality,
                full_page=full_page,
            )
        except Exception as e:
            logger.error("screenshot_failed", error=str(e))
            return b""

    async def get_page_info(self) -> dict:
        """Get basic information about the current page.

        Returns:
            dict with keys: url, title, viewport, scroll_position, launch_strategy.
        """
        try:
            page = await self.get_page()
            scroll = await page.evaluate(
                "() => ({x: window.scrollX, y: window.scrollY})"
            )
            return {
                "url": page.url,
                "title": await page.title(),
                "viewport": {
                    "width": self._viewport_width,
                    "height": self._viewport_height,
                },
                "scroll_position": scroll,
                "launch_strategy": self._launch_strategy,
            }
        except Exception as e:
            return {
                "url": "",
                "title": "",
                "viewport": {
                    "width": self._viewport_width,
                    "height": self._viewport_height,
                },
                "scroll_position": {"x": 0, "y": 0},
                "launch_strategy": self._launch_strategy,
                "error": str(e),
            }

    @property
    def launch_strategy(self) -> str:
        """Return the strategy used to launch the browser."""
        return self._launch_strategy

    @property
    def is_started(self) -> bool:
        """Return True if the browser is started and page is available."""
        return self._page is not None and not self._page.is_closed()
