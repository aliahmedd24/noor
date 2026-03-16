"""PageSummarizerAgent — content extraction and article reading."""

from __future__ import annotations

from collections import defaultdict

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from .schemas import SummaryOutput
from .callbacks import log_tool_errors, emit_tool_start
from .prompts import SUMMARIZER_INSTRUCTION
from .state_helpers import minify_state
from .tools.vision_tools import analyze_current_page, describe_page_aloud
from .tools.page_tools import extract_page_text, get_page_metadata
from .tools.browser_tools import scroll_down


def _build_instruction(ctx: ReadonlyContext) -> str:
    """Build summarizer agent instructions with minified state values."""
    state = dict(ctx.state) if ctx.state else {}
    minified = minify_state(state)
    safe = defaultdict(str, minified)
    return SUMMARIZER_INSTRUCTION.format_map(safe)


summarizer_agent = LlmAgent(
    name="PageSummarizerAgent",
    model="gemini-3.1-pro-preview",
    description=(
        "Reads and summarizes web page content in a clear, concise spoken format. "
        "Extracts article text, search result listings, product details, form "
        "field descriptions, and menu/navigation items. Adapts the summary style "
        "to the page type. Use this agent when the user wants to KNOW what a page "
        "says — reading articles, reviewing search results, understanding form "
        "content, or getting an overview of available links and sections."
    ),
    instruction=_build_instruction,
    output_key="page_summary",
    output_schema=SummaryOutput,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=4096,
        thinking_config=types.ThinkingConfig(
            thinking_level="LOW",
        ),
    ),
    tools=[
        analyze_current_page,
        describe_page_aloud,
        extract_page_text,
        get_page_metadata,
        scroll_down,
    ],
    before_tool_callback=emit_tool_start,
    after_tool_callback=log_tool_errors,
    disallow_transfer_to_peers=True,
)
