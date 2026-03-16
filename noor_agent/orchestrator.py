"""NoorOrchestrator — single LlmAgent with all tools, wrapped in a LoopAgent."""

from __future__ import annotations

from collections import defaultdict

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.base_llm import BaseLlm
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
    click_element_by_text,
    type_into_field,
    select_dropdown_option,
    scroll_down,
    scroll_up,
    go_back_in_browser,
    fill_form,
)
from .tools.vision_tools import analyze_current_page, find_and_click
from .tools.page_tools import extract_page_text, get_accessibility_tree, read_page_aloud
from .tools.state_tools import task_complete, explain_what_happened

# Default model for text mode (non-streaming)
DEFAULT_MODEL = "gemini-3.1-pro-preview"

_ORCHESTRATOR_DESCRIPTION = (
    "Noor is a web task agent for visually impaired users. She navigates "
    "websites, fills forms, clicks buttons, reads content, and narrates "
    "everything so the user stays in control. She has direct access to "
    "browser automation, vision analysis, and content extraction tools."
)

_ORCHESTRATOR_TOOLS = [
    # Navigation & interaction
    navigate_to_url,
    click_element_by_text,
    find_and_click,          # vision-based OR coordinate click
    type_into_field,         # type + optional submit/tab
    select_dropdown_option,
    fill_form,               # batch form filling
    scroll_down,
    scroll_up,
    go_back_in_browser,
    # Vision & content
    analyze_current_page,
    extract_page_text,       # visible DOM text
    get_accessibility_tree,  # ARIA tree (roles, labels, values)
    read_page_aloud,         # structured article narration
    # Session & flow control
    explain_what_happened,
    task_complete,
]


def _build_instruction(ctx: ReadonlyContext) -> str:
    """Build orchestrator instructions with minified state values."""
    state = dict(ctx.state) if ctx.state else {}
    minified = minify_state(state)
    safe = defaultdict(str, minified)
    return ORCHESTRATOR_INSTRUCTION.format_map(safe)


def create_orchestrator(
    model: str | BaseLlm = DEFAULT_MODEL,
    use_planner: bool = True,
) -> LlmAgent:
    """Create an orchestrator LlmAgent.

    Args:
        model: Gemini model ID string or a ``BaseLlm`` instance (e.g. a
            ``Gemini`` subclass with regional Live API routing).
        use_planner: Whether to attach the BuiltInPlanner. Disable for
            native-audio models that do not support extended thinking.

    Returns:
        A fully configured LlmAgent.
    """
    planner = None
    if use_planner:
        planner = BuiltInPlanner(
            thinking_config=types.ThinkingConfig(
                include_thoughts=False,
                thinking_budget=2048,
            )
        )

    return LlmAgent(
        name="NoorOrchestrator",
        model=model,
        description=_ORCHESTRATOR_DESCRIPTION,
        instruction=_build_instruction,
        output_key="orchestrator_output",
        planner=planner,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.3,
        ),
        tools=_ORCHESTRATOR_TOOLS,
        sub_agents=[],
        before_agent_callback=ensure_tools_initialized,
        before_tool_callback=validate_navigator_tool_inputs,
        after_tool_callback=log_tool_errors,
    )


# Default orchestrator instance for text mode
orchestrator_agent = create_orchestrator()
