"""Page content extraction tools for Noor ADK agents.

These tools use Playwright to extract text and metadata directly from the DOM,
complementing the vision-based analysis tools. Useful for getting accurate text
content when the vision model's OCR might be imprecise.
"""

from __future__ import annotations

import structlog

from src.browser.manager import BrowserManager

logger = structlog.get_logger(__name__)

_browser: BrowserManager | None = None


def set_browser_manager(browser: BrowserManager) -> None:
    """Initialize the module's browser manager reference.

    Args:
        browser: The BrowserManager instance to use for page extraction.
    """
    global _browser
    _browser = browser


def _check_browser() -> dict | None:
    """Return an error dict if browser is not initialized, else None."""
    if _browser is None or not _browser.is_started:
        return {
            "status": "error",
            "error": "Browser not started. The browser manager must be "
            "initialized before using page tools.",
        }
    return None


async def extract_page_text(selector: str = "body") -> dict:
    """Extract all visible text content from the current page.

    Uses Playwright to get the inner text of the page body or a specific
    element. Useful for reading articles, extracting search results, or
    getting the full text content of any page.

    The extracted text preserves the visual ordering of content on the page,
    skipping hidden elements.

    Args:
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
        page = await _browser.get_page()
        info = await _browser.get_page_info()

        # Try the requested selector, fall back to body
        try:
            element = page.locator(selector).first
            text = await element.inner_text(timeout=5000)
        except Exception:
            text = await page.locator("body").inner_text(timeout=5000)

        char_count = len(text)
        # Truncate to avoid overwhelming the LLM context
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
        return {"status": "error", "text": "", "char_count": 0, "url": "", "title": "", "error": str(e)}


async def get_page_metadata() -> dict:
    """Get metadata about the current page including URL, title, and basic info.

    Returns structured information about the currently loaded page that helps
    agents understand context without needing a full vision analysis.

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
        info = await _browser.get_page_info()
        page = await _browser.get_page()

        # Check if page has meaningful content
        body_text = await page.locator("body").inner_text(timeout=3000)
        has_content = len(body_text.strip()) > 10

        return {
            "status": "success",
            "url": info["url"],
            "title": info["title"],
            "viewport": info["viewport"],
            "scroll_position": info["scroll"],
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
