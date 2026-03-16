"""PageSummarizerAgent — content extraction and article reading."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from src.agents.schemas import SummaryOutput
from src.agents.callbacks import log_tool_errors
from src.agents.state_helpers import minify_state
from src.tools.vision_tools import analyze_current_page, describe_page_aloud
from src.tools.page_tools import extract_page_text, get_page_metadata
from src.tools.browser_tools import scroll_down

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "summarizer.txt").read_text()


def _build_instruction(ctx: ReadonlyContext) -> str:
    """Build summarizer agent instructions with minified state values."""
    from collections import defaultdict

    state = dict(ctx.state) if ctx.state else {}
    minified = minify_state(state)
    safe = defaultdict(str, minified)
    return _INSTRUCTIONS.format_map(safe)


summarizer_agent = LlmAgent(
    name="PageSummarizerAgent",
    model="gemini-2.5-flash",
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
            thinking_level="MINIMAL",
        ),
    ),
    tools=[
        analyze_current_page,
        describe_page_aloud,
        extract_page_text,
        get_page_metadata,
        scroll_down,
    ],
    after_tool_callback=log_tool_errors,
    disallow_transfer_to_peers=True,
)
