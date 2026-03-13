"""Agent lifecycle callbacks — lazy initialization of browser and vision tools."""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_initialized = False


async def ensure_tools_initialized(callback_context) -> None:
    """Initialize browser and vision tool dependencies on first agent run.

    This callback is attached to the root orchestrator as a
    ``before_agent_callback``. It starts the BrowserManager and
    ScreenAnalyzer singletons the first time the agent processes input,
    then injects them into the tool modules.

    Args:
        callback_context: ADK CallbackContext (unused beyond triggering init).

    Returns:
        None — returning None tells ADK to continue normal agent processing.
    """
    global _initialized
    if _initialized:
        return None

    logger.info("initializing_tool_dependencies")

    from src.config import settings
    from src.browser.manager import BrowserManager
    from src.vision.analyzer import ScreenAnalyzer
    from src.tools import browser_tools, vision_tools

    # Start browser
    headless = settings.noor_browser_headless
    channel = settings.noor_browser_channel or None
    cdp_endpoint = settings.noor_cdp_endpoint or None

    browser = BrowserManager(
        headless=headless,
        channel=channel,
        cdp_endpoint=cdp_endpoint,
    )
    await browser.start()

    # Create vision analyzer
    analyzer = ScreenAnalyzer()

    # Inject into tool modules
    browser_tools.set_browser_manager(browser)
    vision_tools.set_browser_manager(browser)
    vision_tools.set_screen_analyzer(analyzer)

    _initialized = True
    logger.info(
        "tool_dependencies_initialized",
        browser_strategy=browser.launch_strategy,
    )
    return None
