"""Browser automation tools for Noor ADK agents.

Each function in this module is an ADK tool that the agent can invoke
to interact with the browser. Tools access the shared BrowserManager
instance via the module-level singleton.

IMPORTANT: Every tool function MUST:
1. Have comprehensive docstrings (ADK reads these)
2. Use simple types for parameters (str, int, float, bool, list, dict)
3. Return a dict with a 'status' key ('success' or 'error')
4. Never raise exceptions — always return error information in the dict
"""

from __future__ import annotations

import structlog

from src.browser.manager import BrowserManager
from src.browser import actions

logger = structlog.get_logger(__name__)

_browser: BrowserManager | None = None


def set_browser_manager(browser: BrowserManager) -> None:
    """Initialize the module's browser manager reference.

    Args:
        browser: The BrowserManager instance to use for all tool calls.
    """
    global _browser
    _browser = browser


def _check_browser() -> dict | None:
    """Return an error dict if browser is not initialized, else None."""
    if _browser is None or not _browser.is_started:
        return {
            "status": "error",
            "error": "Browser not started. The browser manager must be "
            "initialized before using browser tools.",
        }
    return None


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
    err = _check_browser()
    if err:
        return err
    try:
        result = await _browser.navigate(url)
        if result["success"]:
            return {
                "status": "success",
                "url": result["url"],
                "title": result["title"],
                "error": None,
            }
        return {
            "status": "error",
            "url": result["url"],
            "title": result["title"],
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "url": url, "title": "", "error": str(e)}


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
    err = _check_browser()
    if err:
        return err
    try:
        result = await actions.click_element(
            _browser, coordinates=(x, y)
        )
        return {
            "status": "success" if result["success"] else "error",
            "url": result["url"],
            "title": result["title"],
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "url": "", "title": "", "error": str(e)}


async def click_element_by_text(text: str) -> dict:
    """Click an element that contains specific visible text.

    Use this tool as a fallback when coordinate-based clicking fails
    or when the element's text is known but its exact position is uncertain.

    Args:
        text: The visible text of the element to click
              (e.g., "Sign In", "Submit", "Next").

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - url: Current page URL
        - title: Current page title
        - error: Error message if element not found or click failed
    """
    err = _check_browser()
    if err:
        return err
    try:
        result = await actions.click_element(_browser, description=text)
        return {
            "status": "success" if result["success"] else "error",
            "url": result["url"],
            "title": result["title"],
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "url": "", "title": "", "error": str(e)}


async def type_into_field(text: str, x: int = 0, y: int = 0) -> dict:
    """Type text into the currently focused input field, or click coordinates first.

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
    err = _check_browser()
    if err:
        return err
    try:
        coords = (x, y) if x > 0 and y > 0 else None
        result = await actions.type_text(
            _browser, text=text, coordinates=coords
        )
        return {
            "status": "success" if result["success"] else "error",
            "typed_text": text,
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "typed_text": "", "error": str(e)}


async def scroll_down(pixels: int = 500) -> dict:
    """Scroll the page downward to see more content.

    Use this tool when you need to see content below the current viewport,
    such as when looking for more search results, reading long articles,
    or finding elements that are not visible on screen.

    Args:
        pixels: Number of pixels to scroll down. Default is 500
                (about half the viewport).

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - scroll_y: New vertical scroll position
        - error: Error message if scroll failed
    """
    err = _check_browser()
    if err:
        return err
    try:
        result = await actions.scroll_page(
            _browser, direction="down", amount=pixels
        )
        return {
            "status": "success" if result["success"] else "error",
            "scroll_y": result["scroll_position"]["y"],
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "scroll_y": 0, "error": str(e)}


async def scroll_up(pixels: int = 500) -> dict:
    """Scroll the page upward to see previous content.

    Args:
        pixels: Number of pixels to scroll up. Default is 500.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - scroll_y: New vertical scroll position
        - error: Error message if scroll failed
    """
    err = _check_browser()
    if err:
        return err
    try:
        result = await actions.scroll_page(
            _browser, direction="up", amount=pixels
        )
        return {
            "status": "success" if result["success"] else "error",
            "scroll_y": result["scroll_position"]["y"],
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "scroll_y": 0, "error": str(e)}


async def press_enter() -> dict:
    """Press the Enter/Return key.

    Use this after typing text in a search box or form field to submit it.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - error: Error message if key press failed
    """
    err = _check_browser()
    if err:
        return err
    try:
        result = await actions.press_key(_browser, "Enter")
        return {
            "status": "success" if result["success"] else "error",
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def press_tab() -> dict:
    """Press the Tab key to move focus to the next form element.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - error: Error message if key press failed
    """
    err = _check_browser()
    if err:
        return err
    try:
        result = await actions.press_key(_browser, "Tab")
        return {
            "status": "success" if result["success"] else "error",
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def go_back_in_browser() -> dict:
    """Navigate the browser back to the previous page.

    Use this when the user wants to go back, or when a navigation
    led to an unexpected page.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - url: The URL after going back
        - title: The page title after going back
        - error: Error message if navigation failed
    """
    err = _check_browser()
    if err:
        return err
    try:
        result = await actions.go_back(_browser)
        return {
            "status": "success" if result["success"] else "error",
            "url": result["url"],
            "title": result["title"],
            "error": result["error"],
        }
    except Exception as e:
        return {"status": "error", "url": "", "title": "", "error": str(e)}


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
        - error: Error message if screenshot failed
    """
    err = _check_browser()
    if err:
        return err
    try:
        from src.browser.screenshot import capture_viewport

        result = await capture_viewport(_browser)
        if result.error:
            return {
                "status": "error",
                "description": "",
                "url": result.url,
                "title": result.title,
                "error": result.error,
            }
        return {
            "status": "success",
            "description": (
                f"Screenshot captured ({result.width}x{result.height}) "
                f"of {result.url}"
            ),
            "url": result.url,
            "title": result.title,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "description": "",
            "url": "",
            "title": "",
            "error": str(e),
        }


async def get_current_page_url() -> dict:
    """Get the URL and title of the currently loaded page.

    Returns:
        A dictionary with:
        - status: 'success'
        - url: Current page URL
        - title: Current page title
        - error: Error message if retrieval failed
    """
    err = _check_browser()
    if err:
        return err
    try:
        info = await _browser.get_page_info()
        return {
            "status": "success",
            "url": info["url"],
            "title": info["title"],
            "error": info.get("error"),
        }
    except Exception as e:
        return {"status": "error", "url": "", "title": "", "error": str(e)}
