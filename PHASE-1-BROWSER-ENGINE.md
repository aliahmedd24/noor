# PHASE 1: BROWSER AUTOMATION & SCREENSHOT ENGINE

## Objective

Build the foundational browser control layer that Noor uses to interact with the web. This phase delivers a fully functional headless browser managed via Playwright, capable of navigation, element interaction, screenshot capture, and viewport management. All browser operations are exposed as async Python functions that will later be wrapped as ADK tools.

**Critical Design Goal:** The browser layer MUST work reliably across Windows (local dev), WSL2, and Linux containers (Cloud Run) without requiring manual troubleshooting. This is achieved through a **multi-strategy launch system** that adapts to the host environment automatically.

---

## 1.0 — KNOWN PLAYWRIGHT + WINDOWS PITFALLS & MITIGATIONS

This section documents every known failure mode and the architectural decisions that prevent them. Claude Code MUST follow these rules when implementing the browser layer.

### Pitfall 1: Chromium Binary Download Failures (Windows)

**Problem:** `playwright install chromium` frequently fails on Windows — corrupt downloads, path-length issues in `%USERPROFILE%\AppData\Local\ms-playwright`, permission errors, and version mismatches between the Playwright Python package and the bundled Chromium build.

**Mitigation:** On Windows local dev, **never use bundled Chromium**. Use the `channel` parameter to launch the system-installed Microsoft Edge or Google Chrome instead. These are already present, always up-to-date, and bypass the entire binary download pipeline.

```python
# CORRECT — Windows local dev
browser = await playwright.chromium.launch(channel="msedge", headless=True)

# WRONG — will trigger the download/versioning nightmare
browser = await playwright.chromium.launch(headless=True)
```

**Rule:** `playwright install chromium` is ONLY run inside the Dockerfile for the Linux container build. It is NEVER run on the developer's Windows machine.

### Pitfall 2: Chromium Sandboxing Failures

**Problem:** Playwright's bundled Chromium tries to use OS-level sandboxing (seccomp-bpf on Linux, restricted tokens on Windows). This fails in WSL2, Docker without `--privileged`, and some Windows configurations — producing cryptic "Browser closed unexpectedly" errors.

**Mitigation:** Always pass `--no-sandbox` in launch args. Playwright's own docs default `chromium_sandbox` to `false`. Additionally pass `--disable-gpu` because GPU acceleration is unsupported in headless containers and broken in WSL2.

### Pitfall 3: WSL2 GPU/Rendering Failures

**Problem:** If the developer runs anything through WSL2, Chromium's GPU acceleration fails because WSL doesn't fully support the required Linux kernel capabilities. The browser either crashes immediately or renders black screens.

**Mitigation:** `--disable-gpu` is always included in launch args. Additionally, `--disable-dev-shm-usage` prevents shared memory crashes in memory-constrained environments (Docker, Cloud Run).

### Pitfall 4: Python asyncio Event Loop on Windows

**Problem:** Python's `asyncio` on Windows defaults to `ProactorEventLoop`, which has known issues with subprocess pipe management that Playwright relies on. This causes sporadic "Event loop is closed" or "NotImplementedError" crashes.

**Mitigation:** At the application entry point (`src/main.py`), force `WindowsSelectorEventLoopPolicy` on Windows before any async code runs.

```python
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

**Rule:** This MUST appear before `uvicorn.run()`, before `asyncio.run()`, and before any Playwright imports in test files.

### Pitfall 5: Playwright Version / Browser Version Mismatch

**Problem:** Each Playwright release pins to an exact Chromium revision. Upgrading `playwright` without re-running `playwright install` (or vice versa) causes "executable doesn't exist" errors. On Windows the stale cache in `ms-playwright/` persists across upgrades.

**Mitigation:** By using `channel="msedge"` on Windows, this problem is entirely eliminated — there is no bundled binary to keep in sync. In the Docker build, `playwright install chromium` runs in the same layer as the pip install, so they're always paired.

### Pitfall 6: CDP Connection Drops

**Problem:** When using `connect_over_cdp` to attach to an external browser, the WebSocket connection can drop if the browser process is restarted or if there are network interruptions.

**Mitigation:** The `BrowserManager` includes a `_ensure_connected()` check before every operation, and a `reconnect()` method that re-establishes the connection.

---

## 1.1 — BROWSER MANAGER (`src/browser/manager.py`)

The `BrowserManager` owns the Playwright browser lifecycle and implements a **three-strategy launch system**.

### Multi-Strategy Launch System

The BrowserManager selects its launch strategy based on environment variables, in this priority order:

| Priority | Strategy | Env Var | When to Use |
|----------|----------|---------|-------------|
| 1 | **CDP Connect** | `NOOR_CDP_ENDPOINT` | Attach to an externally-managed browser (advanced debugging, shared browser instances) |
| 2 | **System Browser Channel** | `NOOR_BROWSER_CHANNEL` | **Windows/macOS local dev** — uses pre-installed Edge or Chrome, zero Chromium download needed |
| 3 | **Bundled Playwright Chromium** | *(default)* | **Docker / Cloud Run / CI** — uses the Chromium installed by `playwright install` in the container |

### Full Class Specification

```python
"""
BrowserManager — Multi-strategy Playwright browser lifecycle manager.

Launch Strategy Priority:
  1. CDP Connect   — if NOOR_CDP_ENDPOINT is set, connect to a running browser via
                     Chrome DevTools Protocol. Useful for attaching to an externally
                     launched Chrome/Edge instance.
  2. System Channel — if NOOR_BROWSER_CHANNEL is set (e.g., "msedge", "chrome"),
                     launch the system-installed browser. THIS IS THE RECOMMENDED
                     STRATEGY FOR WINDOWS LOCAL DEV. It bypasses Playwright's bundled
                     Chromium entirely, avoiding download failures, version mismatches,
                     and sandboxing issues.
  3. Bundled Chromium — (default) launch Playwright's bundled Chromium. This is the
                     correct strategy for Docker containers and Cloud Run where
                     `playwright install chromium` was run during the image build.

Design Decisions:
  - Uses async Playwright API exclusively (no sync)
  - Single browser context with single page (simulates one user session)
  - Viewport fixed at 1280x800 for consistent screenshot dimensions sent to Gemini
  - All launch strategies share the same LAUNCH_ARGS for consistency
  - Screenshots are always JPEG for smaller payload to Gemini vision API
  - Every public method returns a structured dict — never raises exceptions to callers

Windows Compatibility:
  - NEVER call `playwright install chromium` on Windows. Use NOOR_BROWSER_CHANNEL=msedge.
  - The asyncio event loop policy must be set to WindowsSelectorEventLoopPolicy before
    this class is used. (Handled in src/main.py and conftest.py.)
  - --no-sandbox and --disable-gpu are always passed to prevent WSL2/container crashes.
"""

import os
import logging
from datetime import datetime
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages a single Playwright browser session for Noor.

    Supports three launch strategies (CDP, system channel, bundled Chromium)
    selected via environment variables. See module docstring for details.
    """

    # Chromium launch arguments applied to ALL strategies.
    # These prevent the most common crash modes across Windows, WSL2, Docker, and Cloud Run.
    LAUNCH_ARGS: list[str] = [
        "--no-sandbox",                         # Required: sandboxing fails in containers and WSL2
        "--disable-gpu",                        # Required: no GPU in headless/container/WSL2
        "--disable-dev-shm-usage",              # Required: /dev/shm is too small in Docker/Cloud Run
        "--disable-extensions",                 # Performance: skip extension loading
        "--disable-background-timer-throttling", # Prevent throttling in background tabs
        "--disable-renderer-backgrounding",     # Keep renderer active when not focused
        "--disable-backgrounding-occluded-windows",
        "--disable-ipc-flooding-protection",    # Prevent IPC limits during rapid screenshot/action loops
        "--disable-translate",                  # Skip translation popups
        "--no-first-run",                       # Skip first-run dialogs
        "--no-default-browser-check",           # Skip default browser prompts
        "--disable-infobars",                   # Hide "Chrome is being controlled" infobar
    ]

    # Fixed viewport dimensions — all Gemini vision prompts reference these exact values.
    # Changing these requires updating all vision prompt coordinate references.
    DEFAULT_VIEWPORT_WIDTH: int = 1280
    DEFAULT_VIEWPORT_HEIGHT: int = 800

    def __init__(
        self,
        headless: bool = True,
        viewport_width: int = DEFAULT_VIEWPORT_WIDTH,
        viewport_height: int = DEFAULT_VIEWPORT_HEIGHT,
    ):
        """
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
        """Launch browser using the appropriate strategy. Call once at app startup.

        Strategy selection (in priority order):
        1. If NOOR_CDP_ENDPOINT env var is set → connect via CDP
        2. If NOOR_BROWSER_CHANNEL env var is set → launch system browser
        3. Otherwise → launch bundled Playwright Chromium

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

        # Create context and page (shared across all strategies)
        if not self._context:
            self._context = await self._browser.new_context(
                viewport={"width": self._viewport_width, "height": self._viewport_height},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            self._context.set_default_timeout(15000)  # 15s timeout for all operations
            self._page = await self._context.new_page()

        logger.info(f"Browser started via {self._launch_strategy} strategy "
                     f"(viewport: {self._viewport_width}x{self._viewport_height})")

    async def _start_cdp(self, endpoint: str) -> None:
        """Strategy 1: Connect to an externally-managed browser via CDP."""
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(endpoint)
            self._launch_strategy = "cdp"
            # Reuse existing context/page if available
            if self._browser.contexts:
                self._context = self._browser.contexts[0]
                if self._context.pages:
                    self._page = self._context.pages[0]
            logger.info(f"Connected to browser via CDP at {endpoint}")
        except Exception as e:
            logger.warning(f"CDP connection to {endpoint} failed: {e}. Falling back.")
            channel = os.getenv("NOOR_BROWSER_CHANNEL")
            if channel:
                await self._start_channel(channel)
            else:
                await self._start_bundled()

    async def _start_channel(self, channel: str) -> None:
        """Strategy 2: Launch a system-installed browser (Edge, Chrome).

        Args:
            channel: Browser channel name. Supported values:
                     "msedge", "chrome", "msedge-dev", "chrome-canary", etc.
        """
        try:
            self._browser = await self._playwright.chromium.launch(
                channel=channel,
                headless=self._headless,
                args=self.LAUNCH_ARGS,
            )
            self._launch_strategy = f"channel:{channel}"
            logger.info(f"Launched system browser via channel '{channel}'")
        except Exception as e:
            logger.warning(f"Channel '{channel}' launch failed: {e}. Falling back to bundled.")
            await self._start_bundled()

    async def _start_bundled(self) -> None:
        """Strategy 3: Launch Playwright's bundled Chromium."""
        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                args=self.LAUNCH_ARGS,
            )
            self._launch_strategy = "bundled_chromium"
            logger.info("Launched bundled Playwright Chromium")
        except Exception as e:
            raise RuntimeError(
                f"All browser launch strategies failed. Last error: {e}\n\n"
                f"TROUBLESHOOTING:\n"
                f"  Windows: Set NOOR_BROWSER_CHANNEL=msedge in your .env file.\n"
                f"           Do NOT run 'playwright install chromium' on Windows.\n"
                f"  Docker:  Ensure 'playwright install chromium' is in Dockerfile.\n"
                f"  WSL2:    Set NOOR_BROWSER_CHANNEL=msedge and run from Windows Python,\n"
                f"           OR use Docker dev container.\n"
                f"  CDP:     Launch Edge manually with:\n"
                f"           msedge --remote-debugging-port=9222 --headless --disable-gpu\n"
                f"           Then set NOOR_CDP_ENDPOINT=http://localhost:9222"
            ) from e

    async def stop(self) -> None:
        """Close browser and clean up all resources. Call at app shutdown."""
        try:
            if self._page and not self._page.is_closed():
                await self._page.close()
            if self._context:
                await self._context.close()
            # Don't close browser if connected via CDP (we don't own it)
            if self._browser and self._launch_strategy != "cdp":
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"Error during browser cleanup: {e}")
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
            raise RuntimeError("Browser not started or page is closed. Call start() first.")
        return self._page

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict:
        """Navigate to a URL and wait for the page to load.

        Args:
            url: The URL to navigate to. Must include protocol (https://).
            wait_until: Playwright wait condition. One of:
                        'load', 'domcontentloaded', 'networkidle', 'commit'.
                        Default: 'domcontentloaded' (fastest reliable option).

        Returns:
            dict with keys:
                success (bool): Whether navigation succeeded.
                url (str): The final URL after any redirects.
                title (str): The page title.
                error (str|None): Error message if navigation failed.
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
            return {
                "success": False,
                "url": url,
                "title": "",
                "error": f"Navigation failed: {str(e)}",
            }

    async def take_screenshot(self, full_page: bool = False, quality: int = 80) -> bytes:
        """Capture a screenshot of the current viewport (or full page).

        Args:
            full_page: If True, capture the entire scrollable page. Default: viewport only.
            quality: JPEG quality 1-100. Default: 80 (good balance of quality/size for Gemini).

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
            logger.error(f"Screenshot failed: {e}")
            return b""

    async def get_page_info(self) -> dict:
        """Get basic information about the current page.

        Returns:
            dict with keys:
                url (str): Current page URL.
                title (str): Current page title.
                viewport (dict): {width, height} of the viewport.
                scroll_position (dict): {x, y} current scroll offsets.
                launch_strategy (str): How the browser was launched.
        """
        try:
            page = await self.get_page()
            scroll = await page.evaluate("() => ({x: window.scrollX, y: window.scrollY})")
            return {
                "url": page.url,
                "title": await page.title(),
                "viewport": {"width": self._viewport_width, "height": self._viewport_height},
                "scroll_position": scroll,
                "launch_strategy": self._launch_strategy,
            }
        except Exception as e:
            return {
                "url": "",
                "title": "",
                "viewport": {"width": self._viewport_width, "height": self._viewport_height},
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
```

---

## 1.2 — ENVIRONMENT CONFIGURATION FOR BROWSER

### `.env.example` additions for browser configuration

```env
# === Browser Configuration ===
# Strategy 1: CDP Connect (advanced — attach to an externally running browser)
# NOOR_CDP_ENDPOINT=http://localhost:9222

# Strategy 2: System browser channel (RECOMMENDED FOR WINDOWS)
# Set to "msedge" or "chrome" to use your system browser.
# This avoids downloading Playwright's bundled Chromium entirely.
NOOR_BROWSER_CHANNEL=msedge

# Strategy 3: Leave both unset to use bundled Playwright Chromium
# (This is the default for Docker/Cloud Run)

# General browser settings
NOOR_BROWSER_HEADLESS=true
```

### Windows Local Dev Quick-Start

```bash
# 1. Install Playwright Python package ONLY (no browser download)
pip install playwright

# 2. Do NOT run this on Windows:
#    playwright install chromium    <-- SKIP THIS

# 3. Set your .env
echo "NOOR_BROWSER_CHANNEL=msedge" >> .env
echo "NOOR_BROWSER_HEADLESS=true" >> .env

# 4. Test it works
python -c "
import asyncio, sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def test():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel='msedge', headless=True,
            args=['--no-sandbox', '--disable-gpu']
        )
        page = await browser.new_page(viewport={'width': 1280, 'height': 800})
        await page.goto('https://www.google.com')
        print(f'OK: {await page.title()}')
        await browser.close()
asyncio.run(test())
"
```

### CDP Fallback (If Channel Strategy Also Fails)

In rare cases where even `channel="msedge"` has issues (corporate proxy, managed browser policies, etc.), launch Edge manually and connect via CDP:

```bash
# Terminal 1: Launch Edge with remote debugging
"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" ^
    --remote-debugging-port=9222 --headless --disable-gpu --no-sandbox

# Terminal 2: Set env and run Noor
set NOOR_CDP_ENDPOINT=http://localhost:9222
python -m uvicorn src.main:app --port 8080
```

### Docker / Cloud Run (Linux Container)

```dockerfile
# In Dockerfile — this is the ONLY place Chromium is installed
RUN pip install --no-cache-dir playwright && \
    playwright install chromium --with-deps

# Do NOT set NOOR_BROWSER_CHANNEL in the container env.
# The BrowserManager will fall through to Strategy 3 (bundled Chromium).
```

---

## 1.3 — ACTION EXECUTOR (`src/browser/actions.py`)

Individual browser action functions. Each function takes a `BrowserManager` instance and action-specific parameters.

### Functions to Implement

```python
async def click_element(browser: BrowserManager, selector: str = None,
                        coordinates: tuple[int, int] = None,
                        description: str = None) -> dict:
    """
    Click an element on the page.

    Supports three targeting strategies (in priority order):
    1. coordinates: Click at exact (x, y) pixel position
    2. selector: Click using CSS selector
    3. description: Click using accessible name/text (uses getByRole/getByText)

    Args:
        browser: The BrowserManager instance.
        selector: CSS selector string.
        coordinates: (x, y) pixel coordinates to click.
        description: Human-readable description for accessible element lookup.

    Returns:
        dict with keys: success (bool), element_text (str|None), error (str|None)
    """


async def type_text(browser: BrowserManager, text: str,
                    selector: str = None,
                    coordinates: tuple[int, int] = None,
                    clear_first: bool = True) -> dict:
    """
    Type text into a form field.

    Args:
        browser: The BrowserManager instance.
        text: The text to type.
        selector: CSS selector of the input field.
        coordinates: (x, y) to click first, then type.
        clear_first: Clear existing text before typing. Default: True.

    Returns:
        dict with keys: success (bool), field_value (str), error (str|None)
    """


async def scroll_page(browser: BrowserManager,
                      direction: str = "down",
                      amount: int = 500) -> dict:
    """
    Scroll the page in a given direction.

    Args:
        browser: The BrowserManager instance.
        direction: 'up', 'down', 'left', 'right'. Default: 'down'.
        amount: Pixels to scroll. Default: 500.

    Returns:
        dict with keys: success (bool), scroll_position (dict), error (str|None)
    """


async def press_key(browser: BrowserManager, key: str) -> dict:
    """
    Press a keyboard key.

    Args:
        browser: The BrowserManager instance.
        key: Key name (e.g., 'Enter', 'Tab', 'Escape', 'Backspace').

    Returns:
        dict with keys: success (bool), error (str|None)
    """


async def go_back(browser: BrowserManager) -> dict:
    """Navigate browser back one page in history."""


async def go_forward(browser: BrowserManager) -> dict:
    """Navigate browser forward one page in history."""


async def wait_for_element(browser: BrowserManager, selector: str,
                           timeout: int = 10000) -> dict:
    """
    Wait for an element to appear on the page.

    Args:
        browser: The BrowserManager instance.
        selector: CSS selector to wait for.
        timeout: Max wait time in milliseconds.

    Returns:
        dict with keys: success (bool), found (bool), error (str|None)
    """
```

### Implementation Notes

- **Coordinate-based clicking is critical** — Gemini vision will identify elements by pixel coordinates on the screenshot. This is the primary interaction method for Noor.
- For coordinate clicks: use `page.mouse.click(x, y)`
- For selector clicks: use `page.click(selector)`
- For description-based: use `page.get_by_role("button", name=description).click()` or `page.get_by_text(description).click()`
- Always add a short `await page.wait_for_timeout(500)` after clicks to allow page updates
- Return structured dicts — never raise exceptions to the agent layer
- Include the current URL and page title in all action return values for agent context
- When using the CDP strategy, `page.mouse.click()` still works identically — CDP mouse events are the same as native Playwright events

---

## 1.4 — SCREENSHOT MODULE (`src/browser/screenshot.py`)

Handles screenshot capture with optimizations for the Gemini vision API.

### Specification

```python
async def capture_viewport(browser: BrowserManager) -> ScreenshotResult:
    """
    Capture the current browser viewport as a JPEG image.

    Returns:
        ScreenshotResult with: image_bytes, width, height, timestamp, url, title
    """


async def capture_viewport_with_grid(browser: BrowserManager,
                                      grid_size: int = 5) -> ScreenshotResult:
    """
    Capture viewport with a coordinate grid overlay.

    Adds a semi-transparent grid with labeled coordinates to help
    Gemini vision identify precise click targets. Grid labels show
    pixel coordinates at intersections.

    Args:
        browser: The BrowserManager instance.
        grid_size: Number of grid divisions per axis. Default: 5 (creates 5x5 grid).

    Returns:
        ScreenshotResult with grid overlay.
    """


async def capture_element(browser: BrowserManager, selector: str) -> ScreenshotResult:
    """
    Capture a screenshot of a specific element.

    Args:
        browser: The BrowserManager instance.
        selector: CSS selector of the element to capture.

    Returns:
        ScreenshotResult of the element, or error if not found.
    """
```

### Pydantic Model

```python
from pydantic import BaseModel
from datetime import datetime


class ScreenshotResult(BaseModel):
    """Result of a screenshot capture operation."""
    image_bytes: bytes
    width: int
    height: int
    timestamp: datetime
    url: str
    title: str
    has_grid_overlay: bool = False
    error: str | None = None
```

### Grid Overlay Implementation

The coordinate grid overlay is a **key feature** for the UI Navigator category. It helps Gemini vision identify precise click coordinates.

- Use Pillow (`PIL`) to draw the grid overlay on the screenshot
- Grid lines should be semi-transparent gray (RGBA: 128, 128, 128, 80)
- Label coordinates at grid intersections in small white text with dark background
- Grid labels format: `(256, 160)` at each intersection
- This gives Gemini explicit coordinate reference points when it identifies interactive elements
- The `grid_size=5` on a 1280x800 viewport creates reference points every 256x160 pixels

---

## 1.5 — BROWSER TOOLS FOR ADK (`src/tools/browser_tools.py`)

These are the ADK-compatible tool functions that wrap the browser actions. Each function MUST have a detailed docstring because ADK uses the docstring for tool selection.

### Critical ADK Tool Convention

ADK tools are plain Python functions. The `google-adk` framework reads the function name, parameter types (from type hints), and the docstring to present tools to the LLM. **The docstring is the tool's API documentation for the model.**

```python
"""
Browser automation tools for Noor.

Each function in this module is an ADK tool that the agent can invoke
to interact with the browser. Tools access the shared BrowserManager
instance via the module-level singleton.

IMPORTANT: Every tool function MUST:
1. Have comprehensive docstrings (ADK reads these)
2. Use simple types for parameters (str, int, float, bool, list, dict)
3. Return a dict with a 'status' key ('success' or 'error')
4. Never raise exceptions — always return error information in the dict
"""

# Module-level browser manager reference (set during app initialization)
_browser: BrowserManager | None = None


def set_browser_manager(browser: BrowserManager) -> None:
    """Initialize the module's browser manager reference."""
    global _browser
    _browser = browser


async def navigate_to_url(url: str) -> dict:
    """Navigate the browser to a specific URL.

    Use this tool when the user wants to go to a website. The URL should be
    a complete URL including https://.

    Examples:
        - "Go to Google" -> navigate_to_url("https://www.google.com")
        - "Open BBC News" -> navigate_to_url("https://www.bbc.com/news")

    Args:
        url: The full URL to navigate to (must include https://).

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - url: The current page URL after navigation
        - title: The page title
        - error: Error message if navigation failed
    """


async def click_at_coordinates(x: int, y: int) -> dict:
    """Click at specific pixel coordinates on the current page.

    Use this tool when you have identified an interactive element
    (button, link, input field, etc.) from the screenshot analysis
    and know its approximate pixel coordinates.

    The coordinate system origin (0,0) is at the top-left corner of the viewport.
    The viewport is 1280 pixels wide and 800 pixels tall.

    Args:
        x: Horizontal pixel coordinate (0-1280, left to right).
        y: Vertical pixel coordinate (0-800, top to bottom).

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - url: Current page URL (may change if a link was clicked)
        - title: Current page title
        - error: Error message if click failed
    """


async def click_element_by_text(text: str) -> dict:
    """Click an element that contains specific visible text.

    Use this tool as a fallback when coordinate-based clicking fails
    or when the element's text is known but its exact position is uncertain.

    Args:
        text: The visible text of the element to click (e.g., "Sign In", "Submit", "Next").

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - url: Current page URL
        - title: Current page title
        - error: Error message if element not found or click failed
    """


async def type_into_field(text: str, x: int = 0, y: int = 0) -> dict:
    """Type text into the currently focused input field, or click coordinates first then type.

    Use this tool to fill in form fields, search boxes, or text areas.
    If x and y are provided (non-zero), the tool clicks at those coordinates
    first to focus the field, then types the text.

    Args:
        text: The text to type into the field.
        x: Optional x-coordinate to click before typing. Use 0 to skip.
        y: Optional y-coordinate to click before typing. Use 0 to skip.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - typed_text: The text that was typed
        - error: Error message if typing failed
    """


async def scroll_down(pixels: int = 500) -> dict:
    """Scroll the page downward to see more content.

    Use this tool when you need to see content below the current viewport,
    such as when looking for more search results, reading long articles,
    or finding elements that are not visible on screen.

    Args:
        pixels: Number of pixels to scroll down. Default is 500 (about half the viewport).

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - scroll_y: New vertical scroll position
    """


async def scroll_up(pixels: int = 500) -> dict:
    """Scroll the page upward to see previous content.

    Args:
        pixels: Number of pixels to scroll up. Default is 500.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - scroll_y: New vertical scroll position
    """


async def press_enter() -> dict:
    """Press the Enter/Return key.

    Use this after typing text in a search box or form field to submit it.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
    """


async def press_tab() -> dict:
    """Press the Tab key to move focus to the next form element.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
    """


async def go_back_in_browser() -> dict:
    """Navigate the browser back to the previous page.

    Use this when the user wants to go back, or when a navigation
    led to an unexpected page.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - url: The URL after going back
        - title: The page title after going back
    """


async def take_screenshot_of_page() -> dict:
    """Capture a screenshot of the current browser viewport.

    Use this tool to see what is currently displayed on the page.
    The screenshot will be analyzed to understand the page layout,
    identify interactive elements, and determine the current state.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - description: A note that the screenshot has been captured
        - url: Current page URL
        - title: Current page title
    """


async def get_current_page_url() -> dict:
    """Get the URL and title of the currently loaded page.

    Returns:
        A dictionary with:
        - status: 'success'
        - url: Current page URL
        - title: Current page title
    """
```

---

## 1.6 — IMPLEMENTATION ORDER

1. **`src/browser/manager.py`** — BrowserManager class with multi-strategy launch
2. **`src/browser/actions.py`** — All action functions
3. **`src/browser/screenshot.py`** — Screenshot capture + grid overlay
4. **`src/tools/browser_tools.py`** — ADK tool wrappers
5. **`src/browser/__init__.py`** — Export BrowserManager
6. **`tests/conftest.py`** — Shared fixtures with Windows event loop policy
7. **`tests/test_browser_tools.py`** — Integration tests

---

## 1.7 — ACCEPTANCE CRITERIA

- [ ] `BrowserManager` launches via `channel="msedge"` on Windows with `NOOR_BROWSER_CHANNEL=msedge`
- [ ] `BrowserManager` launches via bundled Chromium in Docker when no channel is set
- [ ] `BrowserManager` falls back gracefully: CDP → channel → bundled → clear error message
- [ ] Error message on total failure includes Windows-specific troubleshooting steps
- [ ] `navigate()` successfully loads a page and returns url + title
- [ ] `take_screenshot()` returns valid JPEG bytes (verify `\xff\xd8` magic bytes)
- [ ] Coordinate-based click works at specified (x, y) positions
- [ ] Text typing works into form fields (test with Google search)
- [ ] Grid overlay screenshot shows labeled coordinate intersections
- [ ] All ADK tool functions have comprehensive docstrings
- [ ] All tool functions return `dict` with `status` key — never raise
- [ ] End-to-end test: navigate to google.com → type "hello" in search → press enter → capture screenshot
- [ ] Browser works in headless mode (Cloud Run requirement)
- [ ] No `playwright install chromium` commands anywhere in Windows dev setup instructions

---

## 1.8 — TEST SETUP & SCENARIOS

### `tests/conftest.py` — Shared Test Configuration

```python
"""
Shared pytest configuration for Noor tests.

CRITICAL: Sets the Windows-compatible asyncio event loop policy
before any async tests run. Without this, Playwright subprocess
management fails on Windows with ProactorEventLoop errors.
"""
import sys
import pytest

# Fix Windows asyncio event loop BEFORE any async imports
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
async def browser():
    """Provide a started BrowserManager for tests.

    Uses the same multi-strategy launch as production:
    - Set NOOR_BROWSER_CHANNEL=msedge in your .env for Windows
    - Leave unset in CI/Docker for bundled Chromium
    """
    from src.browser.manager import BrowserManager
    bm = BrowserManager(headless=True)
    await bm.start()
    yield bm
    await bm.stop()
```

### `tests/test_browser_tools.py`

```python
"""Integration tests for the browser automation layer."""
import pytest


async def test_launch_strategy_is_set(browser):
    """Verify that the browser launched with a known strategy."""
    assert browser.launch_strategy in (
        "cdp", "channel:msedge", "channel:chrome", "bundled_chromium"
    )
    assert browser.is_started


async def test_navigate_and_screenshot(browser):
    """Test basic navigation and screenshot capture."""
    result = await browser.navigate("https://www.google.com")
    assert result["success"] is True
    assert "google" in result["url"].lower()

    screenshot = await browser.take_screenshot()
    assert len(screenshot) > 0
    # Verify JPEG magic bytes
    assert screenshot[:2] == b'\xff\xd8'


async def test_page_info(browser):
    """Test page info retrieval."""
    await browser.navigate("https://www.google.com")
    info = await browser.get_page_info()
    assert info["viewport"]["width"] == 1280
    assert info["viewport"]["height"] == 800
    assert "google" in info["url"].lower()


async def test_navigate_failure_returns_error(browser):
    """Test that navigation failures return structured errors, not exceptions."""
    result = await browser.navigate("https://this-domain-does-not-exist-xyz.com")
    assert result["success"] is False
    assert result["error"] is not None
    assert isinstance(result["error"], str)


async def test_google_search_flow(browser):
    """Test the full Google search flow used in the demo."""
    await browser.navigate("https://www.google.com")
    page = await browser.get_page()

    # Find and interact with search box
    search_box = page.get_by_role("combobox", name="Search")
    await search_box.fill("Playwright Python")
    await page.keyboard.press("Enter")
    await page.wait_for_load_state("domcontentloaded")

    info = await browser.get_page_info()
    assert "Playwright" in info["title"] or "playwright" in info["url"].lower()


async def test_coordinate_click(browser):
    """Test clicking at specific coordinates."""
    await browser.navigate("https://www.google.com")
    page = await browser.get_page()
    # Click in the center of the viewport (should not crash)
    await page.mouse.click(640, 400)
    # Verify page is still responsive
    info = await browser.get_page_info()
    assert info["url"] is not None


async def test_screenshot_is_jpeg_at_correct_dimensions(browser):
    """Verify screenshot format and approximate dimensions."""
    await browser.navigate("https://www.google.com")
    screenshot = await browser.take_screenshot()

    # Verify JPEG
    assert screenshot[:2] == b'\xff\xd8'
    assert screenshot[-2:] == b'\xff\xd9'

    # Verify dimensions by decoding with Pillow
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(screenshot))
    assert img.width == 1280
    assert img.height == 800
```

---

## 1.9 — NOTES FOR CLAUDE CODE

### MUST DO
- Set `asyncio.WindowsSelectorEventLoopPolicy()` at the top of EVERY entry point: `src/main.py`, `tests/conftest.py`, any standalone scripts
- Read `NOOR_BROWSER_CHANNEL` and `NOOR_CDP_ENDPOINT` from environment in `BrowserManager.start()`
- Include the full `LAUNCH_ARGS` list on every `chromium.launch()` call — including in the channel strategy
- Always return dicts from action functions, never raise
- Close browser gracefully in `stop()` but DO NOT close a CDP-connected browser (we don't own it)
- Log which strategy was used on startup — this is invaluable for debugging

### MUST NOT DO
- Do NOT call `playwright install chromium` in any setup script, Makefile, or documentation for Windows
- Do NOT use `playwright.sync_api` anywhere — async only
- Do NOT hardcode a specific Chromium executable path
- Do NOT use `headless=False` in CI or Cloud Run
- Do NOT assume the bundled Chromium binary exists on the developer's machine
- Do NOT catch exceptions silently — always log them, then return structured error dicts
