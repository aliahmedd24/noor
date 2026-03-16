"""Page content extraction tools for Noor ADK agents.

These tools use Playwright to extract text and metadata directly from the DOM,
complementing the vision-based analysis tools.
"""

from __future__ import annotations

import structlog

from google.adk.tools import ToolContext

logger = structlog.get_logger(__name__)

_service = None  # BrowserService instance


def set_browser_service(service) -> None:
    """Initialize the module's browser service reference.

    Args:
        service: The BrowserService instance to use for page extraction.
    """
    global _service
    _service = service


def _check_browser() -> dict | None:
    """Return an error dict if browser is not initialized, else None."""
    if _service is None or not _service.is_started:
        return {
            "status": "error",
            "error": "Browser not started. The browser service must be "
            "initialized before using page tools.",
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


async def extract_page_text(tool_context: ToolContext, selector: str = "body") -> dict:
    """Extract all visible text content from the current page.

    Uses Playwright to get the inner text of the page body or a specific
    element. Useful for reading articles, extracting search results, or
    getting the full text content of any page.

    Args:
        tool_context: ADK tool context for session state updates.
        selector: CSS selector for the element to extract text from.
                  Default is 'body' which gets all visible text.
                  Use 'main' or 'article' to focus on primary content.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - text: Extracted page text content (truncated to 8000 chars)
        - char_count: Total character count before truncation
        - url: Current page URL
        - title: Current page title
        - error: Error message if status is 'error'
    """
    err = _check_browser()
    if err:
        return err
    try:
        page = await _service.browser.get_page()
        info = await _service.browser.get_page_info()

        await _update_page_state(tool_context)

        # Try the requested selector, fall back to body
        try:
            element = page.locator(selector).first
            text = await element.inner_text(timeout=5000)
        except Exception:
            text = await page.locator("body").inner_text(timeout=5000)

        char_count = len(text)
        if len(text) > 8000:
            text = text[:8000] + "\n\n[... content truncated ...]"

        return {
            "status": "success",
            "text": text,
            "char_count": char_count,
            "url": info["url"],
            "title": info["title"],
            "error": None,
        }
    except Exception as e:
        logger.error("extract_page_text_failed", error=str(e))
        return {
            "status": "error",
            "text": "",
            "char_count": 0,
            "url": "",
            "title": "",
            "error": str(e),
        }


async def get_page_metadata(tool_context: ToolContext) -> dict:
    """Get metadata about the current page including URL, title, and basic info.

    Returns structured information about the currently loaded page that helps
    agents understand context without needing a full vision analysis.

    Args:
        tool_context: ADK tool context for session state updates.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - url: Current page URL
        - title: Current page title
        - viewport: Viewport dimensions
        - scroll_position: Current scroll position
        - has_content: Whether the page has loaded meaningful content
        - error: Error message if status is 'error'
    """
    err = _check_browser()
    if err:
        return err
    try:
        info = await _service.browser.get_page_info()
        page = await _service.browser.get_page()

        await _update_page_state(tool_context)

        body_text = await page.locator("body").inner_text(timeout=3000)
        has_content = len(body_text.strip()) > 10

        return {
            "status": "success",
            "url": info["url"],
            "title": info["title"],
            "viewport": info["viewport"],
            "scroll_position": info["scroll_position"],
            "has_content": has_content,
            "error": None,
        }
    except Exception as e:
        logger.error("get_page_metadata_failed", error=str(e))
        return {
            "status": "error",
            "url": "",
            "title": "",
            "viewport": {},
            "scroll_position": {},
            "has_content": False,
            "error": str(e),
        }


async def get_page_accessibility_tree(tool_context: ToolContext, scope: str = "body") -> dict:
    """Get the accessibility tree of the current page.

    Returns the ARIA structure of the page showing every interactive element
    with its role (button, link, combobox, textbox, etc.), accessible name,
    and current state/value. This is much faster than a screenshot analysis
    and provides the exact labels needed for clicking and typing.

    IMPORTANT: Use this tool to understand the page structure before interacting.
    The tree shows:
    - combobox elements (dropdowns) — click them to open, then select options
    - textbox elements — type into them using their label
    - button elements — click them by name
    - Current values of form fields (e.g., combobox "Where from?": Bremen)

    Args:
        tool_context: ADK tool context for session state updates.
        scope: CSS selector to scope the tree. Default 'body' for full page.
               Use 'form', 'main', or '[role=\"search\"]' to focus on specific areas.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - tree: The accessibility tree as formatted text (YAML-like)
        - url: Current page URL
        - title: Current page title
        - error: Error message if status is 'error'
    """
    err = _check_browser()
    if err:
        return err
    try:
        page = await _service.browser.get_page()
        info = await _service.browser.get_page_info()

        await _update_page_state(tool_context)

        try:
            tree = await page.locator(scope).first.aria_snapshot()
        except Exception:
            tree = await page.locator("body").aria_snapshot()

        # Truncate very large trees to keep LLM context manageable
        if len(tree) > 6000:
            tree = tree[:6000] + "\n\n[... tree truncated, use a narrower scope ...]"

        return {
            "status": "success",
            "tree": tree,
            "url": info["url"],
            "title": info["title"],
            "error": None,
        }
    except Exception as e:
        logger.error("get_page_accessibility_tree_failed", error=str(e))
        return {
            "status": "error",
            "tree": "",
            "url": "",
            "title": "",
            "error": str(e),
        }
