"""Integration tests for the browser automation layer."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from src.browser import actions
from src.browser.screenshot import capture_viewport, capture_viewport_with_grid


async def _dismiss_google_consent(page):
    """Dismiss Google's cookie consent dialog if present."""
    try:
        # Try clicking "Accept all" / "Alle akzeptieren" button
        accept_btn = page.locator("button:has-text('Accept all'), button:has-text('Alle akzeptieren'), button:has-text('I agree'), button#L2AGLb").first
        await accept_btn.click(timeout=3000)
        await page.wait_for_timeout(500)
    except Exception:
        pass  # No consent dialog present


async def test_launch_strategy_is_set(browser):
    """Verify that the browser launched with a known strategy."""
    assert browser.launch_strategy in (
        "cdp",
        "channel:msedge",
        "channel:chrome",
        "bundled_chromium",
    )
    assert browser.is_started


async def test_navigate_and_screenshot(browser):
    """Test basic navigation and screenshot capture."""
    result = await browser.navigate("https://www.google.com")
    assert result["success"] is True
    assert "google" in result["url"].lower()

    screenshot = await browser.take_screenshot()
    assert len(screenshot) > 0
    assert screenshot[:2] == b"\xff\xd8"


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


async def test_coordinate_click(browser):
    """Test clicking at specific coordinates."""
    await browser.navigate("https://www.google.com")
    result = await actions.click_element(browser, coordinates=(640, 400))
    assert result["success"] is True
    info = await browser.get_page_info()
    assert info["url"] is not None


async def test_scroll(browser):
    """Test page scrolling."""
    await browser.navigate("https://www.google.com")
    result = await actions.scroll_page(browser, direction="down", amount=300)
    assert result["success"] is True


async def test_press_key(browser):
    """Test keyboard key press."""
    await browser.navigate("https://www.google.com")
    result = await actions.press_key(browser, "Tab")
    assert result["success"] is True


async def test_type_text(browser):
    """Test typing into a field using textarea selector."""
    await browser.navigate("https://www.google.com")
    page = await browser.get_page()
    await _dismiss_google_consent(page)
    search_input = page.locator("textarea[name='q'], input[name='q']").first
    await search_input.click(timeout=10000)
    result = await actions.type_text(browser, "hello world")
    assert result["success"] is True


async def test_screenshot_is_jpeg_at_correct_dimensions(browser):
    """Verify screenshot format and dimensions."""
    await browser.navigate("https://www.google.com")
    screenshot = await browser.take_screenshot()

    assert screenshot[:2] == b"\xff\xd8"
    assert screenshot[-2:] == b"\xff\xd9"

    img = Image.open(io.BytesIO(screenshot))
    assert img.width == 1280
    assert img.height == 800


async def test_capture_viewport(browser):
    """Test the capture_viewport function."""
    await browser.navigate("https://www.google.com")
    result = await capture_viewport(browser)
    assert result.error is None
    assert result.width == 1280
    assert result.height == 800
    assert len(result.image_bytes) > 0
    assert "google" in result.url.lower()


async def test_capture_viewport_with_grid(browser):
    """Test grid overlay screenshot."""
    await browser.navigate("https://www.google.com")
    result = await capture_viewport_with_grid(browser, grid_size=5)
    assert result.error is None
    assert result.has_grid_overlay is True
    assert result.width == 1280
    assert result.height == 800

    img = Image.open(io.BytesIO(result.image_bytes))
    assert img.width == 1280
    assert img.height == 800


async def test_google_search_flow(browser):
    """Test the full Google search flow used in the demo."""
    await browser.navigate("https://www.google.com")
    page = await browser.get_page()
    await _dismiss_google_consent(page)

    search_input = page.locator("textarea[name='q'], input[name='q']").first
    await search_input.fill("Playwright Python", timeout=10000)
    await page.keyboard.press("Enter")
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(2000)

    url = page.url.lower()
    title = (await page.title()).lower()
    # After search, URL should contain search query or "search" path
    assert (
        "playwright" in title
        or "playwright" in url
        or "search" in url
        or "q=" in url
    ), f"Expected search results page, got url={page.url} title={await page.title()}"
