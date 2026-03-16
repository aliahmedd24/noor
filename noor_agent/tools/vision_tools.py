"""Vision analysis tools — screenshot capture + Gemini multimodal analysis.

Each function in this module is an ADK tool that combines screenshot capture
with Gemini vision analysis. Tools access the shared BrowserService instance
via the module-level reference.
"""

from __future__ import annotations

import base64

import structlog

from google.adk.tools import ToolContext

from ..browser.screenshot import capture_viewport
from ..browser import actions

logger = structlog.get_logger(__name__)

_service = None  # BrowserService instance


def set_browser_service(service) -> None:
    """Initialize the module's browser service reference.

    Args:
        service: The BrowserService instance to use for screenshots and analysis.
    """
    global _service
    _service = service


def _check_ready() -> dict | None:
    """Return an error dict if browser or analyzer is not initialized."""
    if _service is None or not _service.is_started:
        return {
            "status": "error",
            "error": "Browser not started. The browser service must be "
            "initialized before using vision tools.",
        }
    if _service.analyzer is None:
        return {
            "status": "error",
            "error": "Screen analyzer not initialized.",
        }
    return None


async def _update_page_state(tool_context: ToolContext) -> None:
    """Write current URL and title to ADK session state."""
    try:
        info = await _service.browser.get_page_info()
        tool_context.state["current_url"] = info["url"]
        tool_context.state["current_title"] = info["title"]
    except Exception:
        pass


async def analyze_current_page(
    tool_context: ToolContext,
    user_intent: str = "",
) -> dict:
    """Capture a screenshot of the current page and analyze its contents.

    This tool takes a screenshot of the browser viewport and uses AI vision
    to understand what is displayed — including text, buttons, links, forms,
    images, and page layout. Use this tool whenever you need to understand
    what is currently on the screen.

    This is Noor's primary way of 'seeing' the web page.

    Args:
        tool_context: ADK tool context for session state updates.
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
        screenshot = await capture_viewport(_service.browser)
        if screenshot.error or not screenshot.image_bytes:
            return {
                "status": "error",
                "error": screenshot.error or "Screenshot capture returned empty bytes",
            }

        await _update_page_state(tool_context)

        scene = await _service.analyzer.analyze_screenshot(
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

        # Encode screenshot for UI streaming (after_tool_callback picks this up)
        screenshot_b64 = base64.b64encode(screenshot.image_bytes).decode("ascii")

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
            "screenshot_base64": screenshot_b64,
            "error": None,
        }
    except Exception as e:
        logger.error("analyze_current_page_failed", error=str(e))
        return {"status": "error", "error": str(e)}


async def describe_page_aloud(tool_context: ToolContext) -> dict:
    """Generate a natural spoken description of the current page for the user.

    Use this tool when the user asks 'what's on the screen?', 'what do you see?',
    'describe this page', 'where am I?', or similar questions about the current
    page content. The description is optimized for being read aloud.

    Args:
        tool_context: ADK tool context for session state updates.

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
        screenshot = await capture_viewport(_service.browser)
        if screenshot.error or not screenshot.image_bytes:
            return {
                "status": "error",
                "narration": "",
                "url": "",
                "title": "",
                "error": screenshot.error or "Screenshot capture returned empty bytes",
            }

        await _update_page_state(tool_context)

        narration = await _service.analyzer.describe_for_narration(
            image_bytes=screenshot.image_bytes,
            page_url=screenshot.url,
            context="",
        )

        screenshot_b64 = base64.b64encode(screenshot.image_bytes).decode("ascii")

        return {
            "status": "success",
            "narration": narration,
            "url": screenshot.url,
            "title": screenshot.title,
            "screenshot_base64": screenshot_b64,
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


async def find_and_click(
    target_description: str,
    tool_context: ToolContext,
    x: int = 0,
    y: int = 0,
) -> dict:
    """Find an element on the page and click it.

    Two modes:
    1. **Coordinate mode** (fast): Pass x and y from a previous vision
       analysis. The tool clicks directly at those pixel coordinates
       without taking a new screenshot.
    2. **Vision mode** (default): Pass only target_description. The tool
       takes a screenshot, uses AI vision to locate the element, then
       clicks its center.

    Use coordinate mode when you already know the position from
    analyze_current_page. Use vision mode when you need to find an
    element by description (e.g., 'click the blue Sign In button').

    The viewport is 1280 x 800 pixels. (0,0) is the top-left corner.

    Args:
        target_description: Natural language description of what to click.
                           Example: "the blue Sign In button", "the first
                           search result", "the search input field".
                           Always provide this even in coordinate mode
                           (for logging).
        tool_context: ADK tool context for session state updates.
        x: Horizontal pixel coordinate (0-1280). Pass >0 with y for
           coordinate mode. Default 0 (triggers vision mode).
        y: Vertical pixel coordinate (0-800). Pass >0 with x for
           coordinate mode. Default 0 (triggers vision mode).

    Returns:
        A dictionary containing:
        - status: 'success' or 'error'
        - clicked: Whether an element was found and clicked
        - target: Description of what was clicked
        - coordinates: The (x, y) coordinates that were clicked, or None
        - error: Error description if the element wasn't found
    """
    # ── Coordinate mode: click directly ──
    if x > 0 and y > 0:
        err = _check_ready()
        if err:
            return err
        try:
            click_result = await actions.click_element(
                _service.browser, coordinates=(x, y)
            )
            await _update_page_state(tool_context)
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
            return {
                "status": "error",
                "clicked": False,
                "target": target_description,
                "coordinates": {"x": x, "y": y},
                "error": str(e),
            }

    # ── Vision mode: screenshot → AI identification → click ──
    err = _check_ready()
    if err:
        return err
    try:
        screenshot = await capture_viewport(_service.browser)
        if screenshot.error or not screenshot.image_bytes:
            return {
                "status": "error",
                "clicked": False,
                "target": target_description,
                "coordinates": None,
                "error": screenshot.error or "Screenshot capture returned empty bytes",
            }

        coords = await _service.analyzer.identify_click_target(
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

        cx, cy = coords
        click_result = await actions.click_element(
            _service.browser, coordinates=(cx, cy)
        )

        await _update_page_state(tool_context)

        screenshot_b64 = base64.b64encode(screenshot.image_bytes).decode("ascii")

        if click_result["success"]:
            return {
                "status": "success",
                "clicked": True,
                "target": target_description,
                "coordinates": {"x": cx, "y": cy},
                "url": click_result["url"],
                "title": click_result["title"],
                "screenshot_base64": screenshot_b64,
                "error": None,
            }
        return {
            "status": "error",
            "clicked": False,
            "target": target_description,
            "coordinates": {"x": cx, "y": cy},
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
