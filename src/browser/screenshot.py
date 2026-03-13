"""Screenshot capture with viewport management and grid overlay.

The coordinate grid overlay is a key feature for the UI Navigator category.
It helps Gemini vision identify precise click coordinates by adding labeled
reference points to the screenshot.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import structlog
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

from src.browser.manager import BrowserManager

logger = structlog.get_logger(__name__)


class ScreenshotResult(BaseModel):
    """Result of a screenshot capture operation."""

    image_bytes: bytes
    width: int
    height: int
    timestamp: datetime
    url: str
    title: str
    has_grid_overlay: bool = False
    error: str | None = None

    model_config = {"arbitrary_types_allowed": True}


async def capture_viewport(browser: BrowserManager) -> ScreenshotResult:
    """Capture the current browser viewport as a JPEG image.

    Args:
        browser: The BrowserManager instance.

    Returns:
        ScreenshotResult with image_bytes, dimensions, and page metadata.
    """
    try:
        page = await browser.get_page()
        image_bytes = await browser.take_screenshot(full_page=False)

        if not image_bytes:
            return ScreenshotResult(
                image_bytes=b"",
                width=0,
                height=0,
                timestamp=datetime.now(timezone.utc),
                url=page.url,
                title=await page.title(),
                error="Screenshot capture returned empty bytes",
            )

        img = Image.open(io.BytesIO(image_bytes))

        return ScreenshotResult(
            image_bytes=image_bytes,
            width=img.width,
            height=img.height,
            timestamp=datetime.now(timezone.utc),
            url=page.url,
            title=await page.title(),
        )
    except Exception as e:
        logger.error("capture_viewport_failed", error=str(e))
        return ScreenshotResult(
            image_bytes=b"",
            width=0,
            height=0,
            timestamp=datetime.now(timezone.utc),
            url="",
            title="",
            error=f"Capture failed: {str(e)}",
        )


async def capture_viewport_with_grid(
    browser: BrowserManager, grid_size: int = 5
) -> ScreenshotResult:
    """Capture viewport with a coordinate grid overlay.

    Adds a semi-transparent grid with labeled coordinates to help
    Gemini vision identify precise click targets. Grid labels show
    pixel coordinates at intersections.

    Args:
        browser: The BrowserManager instance.
        grid_size: Number of grid divisions per axis. Default: 5.

    Returns:
        ScreenshotResult with grid overlay applied.
    """
    try:
        base = await capture_viewport(browser)
        if base.error or not base.image_bytes:
            return base

        img = Image.open(io.BytesIO(base.image_bytes)).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        w, h = img.size
        cell_w = w // grid_size
        cell_h = h // grid_size

        line_color = (128, 128, 128, 80)

        for i in range(1, grid_size):
            x = i * cell_w
            draw.line([(x, 0), (x, h)], fill=line_color, width=1)
        for i in range(1, grid_size):
            y = i * cell_h
            draw.line([(0, y), (w, y)], fill=line_color, width=1)

        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except (OSError, IOError):
            font = ImageFont.load_default()

        for row in range(grid_size + 1):
            for col in range(grid_size + 1):
                x = col * cell_w
                y = row * cell_h
                x = min(x, w - 1)
                y = min(y, h - 1)
                label = f"({x},{y})"

                bbox = draw.textbbox((0, 0), label, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

                lx = max(0, min(x - tw // 2, w - tw - 2))
                ly = max(0, min(y - th // 2, h - th - 2))

                draw.rectangle(
                    [lx - 1, ly - 1, lx + tw + 1, ly + th + 1],
                    fill=(0, 0, 0, 160),
                )
                draw.text((lx, ly), label, fill=(255, 255, 255, 220), font=font)

        composite = Image.alpha_composite(img, overlay).convert("RGB")

        buf = io.BytesIO()
        composite.save(buf, format="JPEG", quality=80)
        grid_bytes = buf.getvalue()

        return ScreenshotResult(
            image_bytes=grid_bytes,
            width=composite.width,
            height=composite.height,
            timestamp=datetime.now(timezone.utc),
            url=base.url,
            title=base.title,
            has_grid_overlay=True,
        )
    except Exception as e:
        logger.error("capture_grid_failed", error=str(e))
        return ScreenshotResult(
            image_bytes=b"",
            width=0,
            height=0,
            timestamp=datetime.now(timezone.utc),
            url="",
            title="",
            error=f"Grid capture failed: {str(e)}",
        )


async def capture_element(
    browser: BrowserManager, selector: str
) -> ScreenshotResult:
    """Capture a screenshot of a specific element.

    Args:
        browser: The BrowserManager instance.
        selector: CSS selector of the element to capture.

    Returns:
        ScreenshotResult of the element, or error if not found.
    """
    try:
        page = await browser.get_page()
        element = await page.query_selector(selector)

        if not element:
            return ScreenshotResult(
                image_bytes=b"",
                width=0,
                height=0,
                timestamp=datetime.now(timezone.utc),
                url=page.url,
                title=await page.title(),
                error=f"Element not found: {selector}",
            )

        image_bytes = await element.screenshot(type="jpeg", quality=80)
        img = Image.open(io.BytesIO(image_bytes))

        return ScreenshotResult(
            image_bytes=image_bytes,
            width=img.width,
            height=img.height,
            timestamp=datetime.now(timezone.utc),
            url=page.url,
            title=await page.title(),
        )
    except Exception as e:
        logger.error("capture_element_failed", selector=selector, error=str(e))
        return ScreenshotResult(
            image_bytes=b"",
            width=0,
            height=0,
            timestamp=datetime.now(timezone.utc),
            url="",
            title="",
            error=f"Element capture failed: {str(e)}",
        )
