"""Browser action executor — click, type, scroll, navigate, wait.

Each function takes a BrowserManager instance and action-specific parameters.
All functions return structured dicts and never raise exceptions to callers.
"""

from __future__ import annotations

import structlog

from .manager import BrowserManager

logger = structlog.get_logger(__name__)

# Common cookie-consent selectors (covers ~90% of sites)
_COOKIE_DISMISS_SELECTORS = [
    # Google-specific
    'button:has-text("Alle ablehnen")',        # Google DE
    'button:has-text("Reject all")',            # Google EN
    'button:has-text("Alle akzeptieren")',      # Google DE accept
    'button:has-text("Accept all")',            # Google EN accept
    # Generic patterns
    '[id*="cookie"] button:has-text("Accept")',
    '[id*="cookie"] button:has-text("Reject")',
    '[id*="consent"] button:has-text("Accept")',
    '[id*="consent"] button:has-text("Reject")',
    '[class*="cookie"] button:has-text("Accept")',
    '[class*="consent"] button:has-text("Accept")',
    'button:has-text("I agree")',
    'button:has-text("Got it")',
    'button:has-text("OK")',
]


async def try_dismiss_cookie_banner(browser: BrowserManager) -> bool:
    """Attempt to dismiss cookie consent banners automatically.

    Tries a list of common cookie/consent selectors. Clicks the first one found.

    Args:
        browser: The BrowserManager instance.

    Returns:
        True if a banner was dismissed, False otherwise.
    """
    try:
        page = await browser.get_page()
        for selector in _COOKIE_DISMISS_SELECTORS:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=500):
                    await locator.click()
                    await page.wait_for_timeout(1000)
                    logger.info("cookie_banner_dismissed", selector=selector)
                    return True
            except Exception:
                continue
    except Exception as e:
        logger.debug("cookie_dismiss_check_failed", error=str(e))
    return False


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
    3. description: Click using accessible name/text (with fallbacks)

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
            clicked = await _click_by_description(page, description)
            if not clicked["success"]:
                return {
                    "success": False,
                    "element_text": None,
                    "url": page.url,
                    "title": await page.title(),
                    "error": clicked["error"],
                }
            element_text = clicked.get("element_text")
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


async def _click_by_description(page, description: str) -> dict:
    """Try multiple strategies to click an element by text description.

    Strategy order (each with a short timeout to avoid wasting iterations):
    1. get_by_text — standard text match
    2. get_by_role("option") — for dropdown menu items
    3. get_by_role("menuitem") — for menu items
    4. get_by_label — for labeled input fields
    5. force click — bypass visibility/interception checks
    """
    strategies = [
        ("get_by_text", lambda: page.get_by_text(description, exact=False).first),
        ("role_option", lambda: page.get_by_role("option", name=description).first),
        ("role_menuitem", lambda: page.get_by_role("menuitem", name=description).first),
        ("role_link", lambda: page.get_by_role("link", name=description).first),
        ("role_button", lambda: page.get_by_role("button", name=description).first),
        ("label", lambda: page.get_by_label(description).first),
    ]

    last_error = ""
    for strategy_name, make_locator in strategies:
        try:
            locator = make_locator()
            # Short timeout — fail fast, try next strategy
            await locator.click(timeout=3000)
            logger.info("click_description", description=description, strategy=strategy_name)
            return {"success": True, "element_text": description}
        except Exception as e:
            last_error = str(e)
            continue

    # Final fallback: force click on get_by_text (bypasses visibility/interception)
    try:
        locator = page.get_by_text(description, exact=False).first
        await locator.click(timeout=3000, force=True)
        logger.info("click_description", description=description, strategy="force")
        return {"success": True, "element_text": description}
    except Exception as e:
        last_error = str(e)

    logger.error("click_failed", error=last_error)
    return {"success": False, "error": f"Click failed: {last_error}"}


async def type_text(
    browser: BrowserManager,
    text: str,
    selector: str | None = None,
    coordinates: tuple[int, int] | None = None,
    clear_first: bool = True,
) -> dict:
    """Type text into a form field.

    Handles autocomplete/combobox fields: after typing, checks for a
    suggestion dropdown and selects the first option if one appears.

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

        # Wait for autocomplete suggestions to appear
        await page.wait_for_timeout(600)

        # Check if an autocomplete/combobox dropdown appeared and select
        # the first suggestion. This handles Google Flights, Google Maps,
        # and other Material Design combobox widgets.
        autocomplete_selected = await _try_select_autocomplete(page)

        field_value = text
        if selector:
            try:
                field_value = await page.input_value(selector)
            except Exception:
                pass

        logger.info(
            "type_text",
            text_length=len(text),
            autocomplete_selected=autocomplete_selected,
        )
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


async def _try_select_autocomplete(page) -> bool:
    """Try to select the first autocomplete suggestion if a dropdown appeared.

    Checks for common autocomplete patterns:
    1. [role="listbox"] with [role="option"] children (ARIA combobox)
    2. ul[role="listbox"] li (Material Design / Google)
    3. Visible dropdown-like overlays

    Returns:
        True if a suggestion was selected, False otherwise.
    """
    # Strategy 1: ARIA listbox with options (Google Flights, most modern UIs)
    try:
        listbox = page.locator('[role="listbox"]').first
        if await listbox.is_visible(timeout=500):
            first_option = listbox.locator('[role="option"]').first
            if await first_option.is_visible(timeout=500):
                await first_option.click(timeout=2000)
                await page.wait_for_timeout(300)
                logger.info("autocomplete_selected", strategy="role_option_click")
                return True
    except Exception:
        pass

    # Strategy 2: Press ArrowDown + Enter (works for most combobox widgets)
    try:
        # Check if the active element is a combobox
        is_combobox = await page.evaluate("""
            () => {
                const el = document.activeElement;
                return el && (
                    el.getAttribute('role') === 'combobox' ||
                    el.getAttribute('aria-haspopup') === 'true' ||
                    el.getAttribute('aria-autocomplete') === 'inline' ||
                    el.getAttribute('aria-autocomplete') === 'list' ||
                    el.getAttribute('aria-autocomplete') === 'both'
                );
            }
        """)
        if is_combobox:
            await page.keyboard.press("ArrowDown")
            await page.wait_for_timeout(200)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(300)
            logger.info("autocomplete_selected", strategy="arrow_down_enter")
            return True
    except Exception:
        pass

    return False


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
