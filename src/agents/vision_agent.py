"""ScreenVisionAgent — screenshot analysis and element identification."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from src.agents.schemas import VisionOutput
from src.agents.callbacks import log_tool_errors
from src.agents.state_helpers import minify_state
from src.tools.vision_tools import (
    analyze_current_page,
    describe_page_aloud,
    find_and_click,
)
from src.tools.browser_tools import take_screenshot_of_page, get_current_page_url

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "vision.txt").read_text()


def _build_instruction(ctx: ReadonlyContext) -> str:
    """Build vision agent instructions with minified state values."""
    from collections import defaultdict

    state = dict(ctx.state) if ctx.state else {}
    minified = minify_state(state)
    safe = defaultdict(str, minified)
    return _INSTRUCTIONS.format_map(safe)


vision_agent = LlmAgent(
    name="ScreenVisionAgent",
    model="gemini-2.5-flash",
    description=(
        "Captures screenshots of the browser viewport and uses AI vision to "
        "understand what is displayed — page layout, text content, images, "
        "and all interactive elements (buttons, links, forms, menus, dropdowns) "
        "with their pixel coordinates. Identifies cookie banners, modals, and "
        "page blockers. Use this agent when you need to SEE the current screen, "
        "find a specific element to interact with, or describe the page to the user."
    ),
    instruction=_build_instruction,
    output_key="vision_analysis",
    output_schema=VisionOutput,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=4096,
        thinking_config=types.ThinkingConfig(
            thinking_level="MINIMAL",
        ),
    ),
    tools=[
        analyze_current_page,
        describe_page_aloud,
        find_and_click,
        take_screenshot_of_page,
        get_current_page_url,
    ],
    after_tool_callback=log_tool_errors,
    disallow_transfer_to_peers=True,
)
