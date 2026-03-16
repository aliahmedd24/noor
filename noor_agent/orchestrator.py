"""NoorOrchestrator — single LlmAgent with all tools, wrapped in a LoopAgent."""

from __future__ import annotations

from collections import defaultdict

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.planners import BuiltInPlanner
from google.genai import types

from .callbacks import (
    ensure_tools_initialized,
    validate_navigator_tool_inputs,
    log_tool_errors,
)
from .prompts import ORCHESTRATOR_INSTRUCTION
from .state_helpers import minify_state
from .tools.browser_tools import (
    navigate_to_url,
    click_at_coordinates,
    click_element_by_text,
    type_into_field,
    press_enter,
    press_tab,
    scroll_down,
    scroll_up,
    go_back_in_browser,
)
from .tools.vision_tools import analyze_current_page, find_and_click
from .tools.page_tools import extract_page_text, get_page_accessibility_tree
from .tools.state_tools import task_complete


def _build_instruction(ctx: ReadonlyContext) -> str:
    """Build orchestrator instructions with minified state values."""
    state = dict(ctx.state) if ctx.state else {}
    minified = minify_state(state)
    safe = defaultdict(str, minified)
    return ORCHESTRATOR_INSTRUCTION.format_map(safe)


orchestrator_agent = LlmAgent(
    name="NoorOrchestrator",
    model="gemini-3.1-pro-preview",
    description=(
        "Noor is a web task agent for visually impaired users. She navigates "
        "websites, fills forms, clicks buttons, reads content, and narrates "
        "everything so the user stays in control. She has direct access to "
        "browser automation, vision analysis, and content extraction tools."
    ),
    instruction=_build_instruction,
    output_key="orchestrator_output",
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False,
            thinking_budget=2048,
        )
    ),
    generate_content_config=types.GenerateContentConfig(
        temperature=0.3,
    ),
    tools=[
        # Navigation & interaction
        navigate_to_url,
        click_at_coordinates,
        click_element_by_text,
        type_into_field,
        press_enter,
        press_tab,
        scroll_down,
        scroll_up,
        go_back_in_browser,
        # Vision
        analyze_current_page,
        find_and_click,
        # Content extraction
        extract_page_text,
        get_page_accessibility_tree,
        # Flow control
        task_complete,
    ],
    sub_agents=[],  # No sub-agents — all tools are direct
    before_agent_callback=ensure_tools_initialized,
    before_tool_callback=validate_navigator_tool_inputs,
    after_tool_callback=log_tool_errors,
)
