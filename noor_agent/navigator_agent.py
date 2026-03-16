"""NavigatorAgent — browser action planning and execution."""

from __future__ import annotations

from collections import defaultdict

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from .schemas import NavigationOutput
from .callbacks import log_tool_errors, validate_navigator_tool_inputs
from .prompts import NAVIGATOR_INSTRUCTION
from .state_helpers import minify_state
from .tools.browser_tools import (
    navigate_to_url,
    click_at_coordinates,
    click_element_by_text,
    type_into_field,
    scroll_down,
    scroll_up,
    press_enter,
    press_tab,
    go_back_in_browser,
)


def _build_instruction(ctx: ReadonlyContext) -> str:
    """Build navigator agent instructions with minified state values."""
    state = dict(ctx.state) if ctx.state else {}
    minified = minify_state(state)
    safe = defaultdict(str, minified)
    return NAVIGATOR_INSTRUCTION.format_map(safe)


navigator_agent = LlmAgent(
    name="NavigatorAgent",
    model="gemini-3.1-pro-preview",
    description=(
        "Executes browser actions: clicking buttons/links at pixel coordinates, "
        "typing text into input fields, scrolling the page, navigating to URLs, "
        "pressing keyboard keys (Enter, Tab), and going back/forward in history. "
        "Use this agent when you need to INTERACT with the web page — performing "
        "clicks, filling forms, submitting searches, or navigating to a new URL. "
        "Requires vision analysis coordinates for precise clicking."
    ),
    instruction=_build_instruction,
    output_key="navigation_result",
    output_schema=NavigationOutput,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=2048,
        thinking_config=types.ThinkingConfig(
            thinking_level="LOW",
        ),
    ),
    tools=[
        navigate_to_url,
        click_at_coordinates,
        click_element_by_text,
        type_into_field,
        scroll_down,
        scroll_up,
        press_enter,
        press_tab,
        go_back_in_browser,
    ],
    before_tool_callback=validate_navigator_tool_inputs,
    after_tool_callback=log_tool_errors,
    disallow_transfer_to_peers=True,
)
