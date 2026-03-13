"""Browser action executor — click, type, scroll, navigate, wait.

Each function takes a BrowserManager instance and action-specific parameters.
All functions return structured dicts and never raise exceptions to callers.
"""

from __future__ import annotations

import structlog

from src.browser.manager import BrowserManager

logger = structlog.get_logger(__name__)


async def click_element(
    browser: BrowserManager,
    selector: str | None = None,
    coordinates: tuple[int, int] | None = None,
    description: str | None = None,
) -> dict:
    """Click an element on the page.

    Supports three targeting strategies (in priority order):
    1. coordinates: Click at exact (x, y) pixel position
    2. selector: Click using CSS selector
    3. description: Click using accessible name/text

    Args:
        browser: The BrowserManager instance.
        selector: CSS selector string.
        coordinates: (x, y) pixel coordinates to click.
        description: Human-readable description for accessible element lookup.

    Returns:
        dict with keys: success, element_text, url, title, error.
    """
    try:
        page = await browser.get_page()
        element_text = None

        if coordinates:
            x, y = coordinates
            await page.mouse.click(x, y)
            logger.info("click_coordinates", x=x, y=y)
        elif selector:
            handle = await page.query_selector(selector)
            if handle:
                element_text = await handle.inner_text()
            await page.click(selector)
            logger.info("click_selector", selector=selector)
        elif description:
            locator = page.get_by_text(description).first
            element_text = await locator.inner_text()
            await locator.click()
            logger.info("click_description", description=description)
        else:
            return {
                "success": False,
                "element_text": None,
                "url": page.url,
                "title": await page.title(),
                "error": "No click target provided (need coordinates, selector, "
                "or description)",
            }

        await page.wait_for_timeout(500)

        return {
            "success": True,
            "element_text": element_text,
            "url": page.url,
            "title": await page.title(),
            "error": None,
        }
    except Exception as e:
        logger.error("click_failed", error=str(e))
        try:
            page = await browser.get_page()
            url = page.url
            title = await page.title()
        except Exception:
            url, title = "", ""
        return {
            "success": False,
            "element_text": None,
            "url": url,
            "title": title,
            "error": f"Click failed: {str(e)}",
        }


async def type_text(
    browser: BrowserManager,
    text: str,
    selector: str | None = None,
    coordinates: tuple[int, int] | None = None,
    clear_first: bool = True,
) -> dict:
    """Type text into a form field.

    Args:
        browser: The BrowserManager instance.
        text: The text to type.
        selector: CSS selector of the input field.
        coordinates: (x, y) to click first, then type.
        clear_first: Clear existing text before typing. Default: True.

    Returns:
        dict with keys: success, field_value, url, title, error.
    """
    try:
        page = await browser.get_page()

        if coordinates:
            x, y = coordinates
            await page.mouse.click(x, y)
            await page.wait_for_timeout(200)
        elif selector:
            await page.click(selector)
            await page.wait_for_timeout(200)

        if clear_first:
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")

        await page.keyboard.type(text, delay=50)

        field_value = text
        if selector:
            try:
                field_value = await page.input_value(selector)
            except Exception:
                pass

        logger.info("type_text", text_length=len(text))
        return {
            "success": True,
            "field_value": field_value,
            "url": page.url,
            "title": await page.title(),
            "error": None,
        }
    except Exception as e:
        logger.error("type_failed", error=str(e))
        return {
            "success": False,
            "field_value": "",
            "url": "",
            "title": "",
            "error": f"Type failed: {str(e)}",
        }


async def scroll_page(
    browser: BrowserManager,
    direction: str = "down",
    amount: int = 500,
) -> dict:
    """Scroll the page in a given direction.

    Args:
        browser: The BrowserManager instance.
        direction: 'up', 'down', 'left', 'right'. Default: 'down'.
        amount: Pixels to scroll. Default: 500.

    Returns:
        dict with keys: success, scroll_position, error.
    """
    try:
        page = await browser.get_page()

        delta_x, delta_y = 0, 0
        if direction == "down":
            delta_y = amount
        elif direction == "up":
            delta_y = -amount
        elif direction == "right":
            delta_x = amount
        elif direction == "left":
            delta_x = -amount

        await page.mouse.wheel(delta_x, delta_y)
        await page.wait_for_timeout(300)

        scroll = await page.evaluate(
            "() => ({x: window.scrollX, y: window.scrollY})"
        )
        logger.info("scroll", direction=direction, amount=amount)
        return {
            "success": True,
            "scroll_position": scroll,
            "error": None,
        }
    except Exception as e:
        logger.error("scroll_failed", error=str(e))
        return {
            "success": False,
            "scroll_position": {"x": 0, "y": 0},
            "error": f"Scroll failed: {str(e)}",
        }


async def press_key(browser: BrowserManager, key: str) -> dict:
    """Press a keyboard key.

    Args:
        browser: The BrowserManager instance.
        key: Key name (e.g., 'Enter', 'Tab', 'Escape', 'Backspace').

    Returns:
        dict with keys: success, url, title, error.
    """
    try:
        page = await browser.get_page()
        await page.keyboard.press(key)
        await page.wait_for_timeout(300)
        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "error": None,
        }
    except Exception as e:
        logger.error("press_key_failed", key=key, error=str(e))
        return {
            "success": False,
            "url": "",
            "title": "",
            "error": f"Key press failed: {str(e)}",
        }


async def go_back(browser: BrowserManager) -> dict:
    """Navigate browser back one page in history.

    Args:
        browser: The BrowserManager instance.

    Returns:
        dict with keys: success, url, title, error.
    """
    try:
        page = await browser.get_page()
        await page.go_back(wait_until="domcontentloaded")
        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "error": None,
        }
    except Exception as e:
        logger.error("go_back_failed", error=str(e))
        return {
            "success": False,
            "url": "",
            "title": "",
            "error": f"Go back failed: {str(e)}",
        }


async def go_forward(browser: BrowserManager) -> dict:
    """Navigate browser forward one page in history.

    Args:
        browser: The BrowserManager instance.

    Returns:
        dict with keys: success, url, title, error.
    """
    try:
        page = await browser.get_page()
        await page.go_forward(wait_until="domcontentloaded")
        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
            "error": None,
        }
    except Exception as e:
        logger.error("go_forward_failed", error=str(e))
        return {
            "success": False,
            "url": "",
            "title": "",
            "error": f"Go forward failed: {str(e)}",
        }


async def wait_for_element(
    browser: BrowserManager,
    selector: str,
    timeout: int = 10000,
) -> dict:
    """Wait for an element to appear on the page.

    Args:
        browser: The BrowserManager instance.
        selector: CSS selector to wait for.
        timeout: Max wait time in milliseconds.

    Returns:
        dict with keys: success, found, error.
    """
    try:
        page = await browser.get_page()
        await page.wait_for_selector(selector, timeout=timeout)
        return {"success": True, "found": True, "error": None}
    except Exception as e:
        logger.warning("wait_for_element_timeout", selector=selector, error=str(e))
        return {
            "success": True,
            "found": False,
            "error": f"Element not found within {timeout}ms: {str(e)}",
        }
