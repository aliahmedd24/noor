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


async def extract_page_text(
    tool_context: ToolContext,
    selector: str = "body",
) -> dict:
    """Extract visible text content from the current page.

    Returns the visible inner text of the page or a specific element.
    Good for reading articles, search results, or any text content.

    For discovering interactive elements (buttons, links, form fields,
    dropdowns), use get_accessibility_tree instead — it is faster and
    shows ARIA roles, labels, and values.

    Args:
        tool_context: ADK tool context for session state updates.
        selector: CSS selector to scope the extraction. Default 'body'
                  for the full page. Use 'main', 'article', 'form', or
                  '[role="search"]' to focus on specific areas.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - text: Extracted visible text content
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


async def get_accessibility_tree(
    tool_context: ToolContext,
    selector: str = "body",
) -> dict:
    """Get the ARIA accessibility tree of the current page.

    Returns every interactive element with its ARIA role (button, link,
    combobox, textbox, heading), accessible name, and current value.
    This is FAST (under 1 second) compared to vision analysis.

    Use this tool as your PRIMARY way to understand the page. It tells you:
    - What form fields exist and their labels (for type_into_field)
    - What buttons and links are available (for click_element_by_text)
    - What dropdowns exist and their current values (for select_dropdown_option)
    - Whether an action changed the page (call before and after)

    Args:
        tool_context: ADK tool context for session state updates.
        selector: CSS selector to scope the tree. Default 'body' for the
                  full page. Use 'form', 'main', 'nav', or
                  '[role="search"]' to focus on specific areas.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - tree: The accessibility tree as structured text
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

        try:
            tree = await page.locator(selector).first.aria_snapshot()
        except Exception:
            tree = await page.locator("body").aria_snapshot()

        if len(tree) > 6000:
            tree = tree[:6000] + "\n\n[... tree truncated, use a narrower selector ...]"

        return {
            "status": "success",
            "tree": tree,
            "char_count": len(tree),
            "url": info["url"],
            "title": info["title"],
            "error": None,
        }
    except Exception as e:
        logger.error("get_accessibility_tree_failed", error=str(e))
        return {
            "status": "error",
            "tree": "",
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


async def read_page_aloud(tool_context: ToolContext) -> dict:
    """Extract the main article or content from the page for natural narration.

    This tool is optimized for reading — it focuses on the primary content
    (article text, main body) while stripping navigation, ads, footers,
    and other noise. The result is structured for natural text-to-speech
    narration with a clear headline, optional byline, and body paragraphs.

    Use this tool when the user says 'read this page', 'read the article',
    'what does it say?', or when you need to narrate page content aloud.

    This is FAST (DOM extraction, <1 second) compared to vision-based
    description tools. Prefer this for reading text content.

    Args:
        tool_context: ADK tool context for session state updates.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - narration: Structured text ready for narration
        - headline: The page/article headline (if found)
        - word_count: Approximate word count
        - content_type: 'article', 'search_results', or 'general'
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

        # Try content-focused selectors in priority order
        content_selectors = [
            "article",
            '[role="main"]',
            "main",
            ".content",
            "#content",
            ".post-content",
            ".article-body",
            ".entry-content",
        ]
        text = ""
        content_type = "general"
        for sel in content_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    text = await loc.inner_text(timeout=5000)
                    if len(text.strip()) > 50:
                        content_type = "article"
                        break
            except Exception:
                continue

        # Fallback to body
        if not text or len(text.strip()) < 50:
            text = await page.locator("body").inner_text(timeout=5000)
            content_type = "general"

        # Try to extract headline
        headline = ""
        for h_sel in ["h1", "article h1", "main h1", '[role="heading"][aria-level="1"]']:
            try:
                h = await page.locator(h_sel).first.inner_text(timeout=1000)
                if h and len(h.strip()) > 2:
                    headline = h.strip()
                    break
            except Exception:
                continue

        if not headline:
            headline = info.get("title", "")

        # Detect search results
        if "search" in info.get("url", "").lower() or "results" in info.get("title", "").lower():
            content_type = "search_results"

        # Build narration
        lines = text.strip().split("\n")
        # Remove very short lines (likely nav items) from the top
        cleaned = [ln.strip() for ln in lines if len(ln.strip()) > 5]

        # Truncate for LLM context
        body = "\n".join(cleaned)
        if len(body) > 6000:
            body = body[:6000] + "\n\n[Content continues below — I can scroll down to read more.]"

        word_count = len(body.split())

        narration_parts = []
        if headline:
            narration_parts.append(f'"{headline}"')
        narration_parts.append(body)

        return {
            "status": "success",
            "narration": "\n\n".join(narration_parts),
            "headline": headline,
            "word_count": word_count,
            "content_type": content_type,
            "url": info["url"],
            "title": info["title"],
            "error": None,
        }
    except Exception as e:
        logger.error("read_page_aloud_failed", error=str(e))
        return {
            "status": "error",
            "narration": "",
            "headline": "",
            "word_count": 0,
            "content_type": "general",
            "url": "",
            "title": "",
            "error": str(e),
        }
