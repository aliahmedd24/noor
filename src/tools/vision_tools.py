"""Vision analysis tools — screenshot capture + Gemini multimodal analysis.

Each function in this module is an ADK tool that combines screenshot capture
with Gemini vision analysis. Tools access the shared BrowserManager and
ScreenAnalyzer instances via module-level singletons.

IMPORTANT: Every tool function MUST:
1. Have comprehensive docstrings (ADK reads these)
2. Use simple types for parameters (str, int, float, bool, list, dict)
3. Return a dict with a 'status' key ('success' or 'error')
4. Never raise exceptions — always return error information in the dict
"""

from __future__ import annotations

import structlog

from src.browser.manager import BrowserManager
from src.browser.screenshot import capture_viewport
from src.browser import actions
from src.vision.analyzer import ScreenAnalyzer

logger = structlog.get_logger(__name__)

_browser: BrowserManager | None = None
_analyzer: ScreenAnalyzer | None = None


def set_browser_manager(browser: BrowserManager) -> None:
    """Initialize the module's browser manager reference.

    Args:
        browser: The BrowserManager instance to use for screenshots.
    """
    global _browser
    _browser = browser


def set_screen_analyzer(analyzer: ScreenAnalyzer) -> None:
    """Initialize the module's screen analyzer reference.

    Args:
        analyzer: The ScreenAnalyzer instance to use for vision calls.
    """
    global _analyzer
    _analyzer = analyzer


def _check_ready() -> dict | None:
    """Return an error dict if browser or analyzer is not initialized."""
    if _browser is None or not _browser.is_started:
        return {
            "status": "error",
            "error": "Browser not started. The browser manager must be "
            "initialized before using vision tools.",
        }
    if _analyzer is None:
        return {
            "status": "error",
            "error": "Screen analyzer not initialized. Call "
            "set_screen_analyzer() before using vision tools.",
        }
    return None


async def analyze_current_page(user_intent: str = "") -> dict:
    """Capture a screenshot of the current page and analyze its contents.

    This tool takes a screenshot of the browser viewport and uses AI vision
    to understand what is displayed — including text, buttons, links, forms,
    images, and page layout. Use this tool whenever you need to understand
    what is currently on the screen.

    This is Noor's primary way of 'seeing' the web page.

    Args:
        user_intent: Optional description of what the user is trying to do.
                     This helps focus the analysis on relevant elements.
                     Example: "looking for the search box" or "trying to find flight prices"

    Returns:
        A dictionary containing:
        - status: 'success' or 'error'
        - page_type: Category of the page (search_results, article, form, etc.)
        - summary: Human-readable summary of the page
        - interactive_elements: List of clickable/interactive elements with coordinates
        - primary_action: The most likely next action
        - has_cookie_banner: Whether a cookie popup needs to be dismissed
        - has_modal: Whether a modal dialog is covering the content
        - error: Error message if status is 'error'
    """
    err = _check_ready()
    if err:
        return err
    try:
        screenshot = await capture_viewport(_browser)
        if screenshot.error or not screenshot.image_bytes:
            return {
                "status": "error",
                "error": screenshot.error or "Screenshot capture returned empty bytes",
            }

        scene = await _analyzer.analyze_screenshot(
            image_bytes=screenshot.image_bytes,
            page_url=screenshot.url,
            page_title=screenshot.title,
            user_intent=user_intent,
        )

        interactive = [
            {
                "type": elem.element_type.value,
                "label": elem.label,
                "x": elem.bounding_box.x,
                "y": elem.bounding_box.y,
                "width": elem.bounding_box.width,
                "height": elem.bounding_box.height,
                "center_x": elem.bounding_box.center[0],
                "center_y": elem.bounding_box.center[1],
                "state": elem.state.value,
                "description": elem.description,
            }
            for elem in scene.interactive_elements
        ]

        return {
            "status": "success",
            "page_type": scene.page_type,
            "summary": scene.summary,
            "visual_layout": scene.visual_layout,
            "primary_action": scene.primary_action,
            "interactive_elements": interactive,
            "interactive_count": len(interactive),
            "has_cookie_banner": scene.has_cookie_banner,
            "has_modal": scene.has_modal,
            "scroll_position": scene.scroll_position,
            "notable_colors": scene.notable_colors,
            "url": screenshot.url,
            "title": screenshot.title,
            "error": None,
        }
    except Exception as e:
        logger.error("analyze_current_page_failed", error=str(e))
        return {"status": "error", "error": str(e)}


async def describe_page_aloud() -> dict:
    """Generate a natural spoken description of the current page for the user.

    Use this tool when the user asks 'what's on the screen?', 'what do you see?',
    'describe this page', 'where am I?', or similar questions about the current
    page content. The description is optimized for being read aloud.

    Returns:
        A dictionary containing:
        - status: 'success' or 'error'
        - narration: A conversational description suitable for text-to-speech
        - url: Current page URL
        - title: Current page title
        - error: Error message if status is 'error'
    """
    err = _check_ready()
    if err:
        return err
    try:
        screenshot = await capture_viewport(_browser)
        if screenshot.error or not screenshot.image_bytes:
            return {
                "status": "error",
                "narration": "",
                "url": "",
                "title": "",
                "error": screenshot.error or "Screenshot capture returned empty bytes",
            }

        narration = await _analyzer.describe_for_narration(
            image_bytes=screenshot.image_bytes,
            page_url=screenshot.url,
            context="",
        )

        return {
            "status": "success",
            "narration": narration,
            "url": screenshot.url,
            "title": screenshot.title,
            "error": None,
        }
    except Exception as e:
        logger.error("describe_page_aloud_failed", error=str(e))
        return {
            "status": "error",
            "narration": "",
            "url": "",
            "title": "",
            "error": str(e),
        }


async def find_and_click(target_description: str) -> dict:
    """Find a specific element on the page by description and click it.

    This tool combines vision analysis with clicking. It takes a screenshot,
    uses AI to find the element matching the description, and clicks its
    center coordinates.

    Use this for commands like 'click the sign in button', 'open the first result',
    'click the search box'.

    Args:
        target_description: Natural language description of what to click.
                           Example: "the blue Sign In button", "the first search result",
                           "the search input field"

    Returns:
        A dictionary containing:
        - status: 'success' or 'error'
        - clicked: Whether an element was found and clicked
        - target: Description of what was clicked
        - coordinates: The (x, y) coordinates that were clicked, or None
        - error: Error description if the element wasn't found
    """
    err = _check_ready()
    if err:
        return err
    try:
        screenshot = await capture_viewport(_browser)
        if screenshot.error or not screenshot.image_bytes:
            return {
                "status": "error",
                "clicked": False,
                "target": target_description,
                "coordinates": None,
                "error": screenshot.error or "Screenshot capture returned empty bytes",
            }

        coords = await _analyzer.identify_click_target(
            image_bytes=screenshot.image_bytes,
            target_description=target_description,
        )

        if coords is None:
            return {
                "status": "error",
                "clicked": False,
                "target": target_description,
                "coordinates": None,
                "error": f"Could not find '{target_description}' on the current page.",
            }

        x, y = coords
        click_result = await actions.click_element(
            _browser, coordinates=(x, y)
        )

        if click_result["success"]:
            return {
                "status": "success",
                "clicked": True,
                "target": target_description,
                "coordinates": {"x": x, "y": y},
                "url": click_result["url"],
                "title": click_result["title"],
                "error": None,
            }
        return {
            "status": "error",
            "clicked": False,
            "target": target_description,
            "coordinates": {"x": x, "y": y},
            "error": click_result["error"],
        }
    except Exception as e:
        logger.error(
            "find_and_click_failed",
            target=target_description,
            error=str(e),
        )
        return {
            "status": "error",
            "clicked": False,
            "target": target_description,
            "coordinates": None,
            "error": str(e),
        }
