"""NoorOrchestrator — root LLM agent that delegates to sub-agents."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.google_llm import Gemini
from google.genai import types

from src.agents.callbacks import ensure_tools_initialized
from src.agents.state_helpers import minify_state
from src.tools.state_tools import get_state_detail

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "orchestrator.txt").read_text()


def _build_instruction(ctx: ReadonlyContext) -> str:
    """Build orchestrator instructions with minified state values."""
    from collections import defaultdict

    state = dict(ctx.state) if ctx.state else {}
    minified = minify_state(state)
    safe = defaultdict(str, minified)
    return _INSTRUCTIONS.format_map(safe)


orchestrator_agent = LlmAgent(
    name="NoorOrchestrator",
    model=Gemini(model="gemini-2.5-flash", use_interactions_api=True),
    description=(
        "Noor is the main conversational coordinator for visually impaired "
        "users navigating the web. Noor manages the conversation, understands "
        "user intent, and delegates to the appropriate specialist: vision "
        "analysis for seeing the screen, navigation for clicking/typing/scrolling, "
        "or summarization for reading page content aloud. Noor always narrates "
        "what is happening so the user knows the current state. Handles greetings, "
        "clarifying questions, and ambiguous requests directly without delegating."
    ),
    instruction=_build_instruction,
    output_key="orchestrator_output",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.5,
        max_output_tokens=4096,
        thinking_config=types.ThinkingConfig(
            thinking_level="HIGH",
        ),
    ),
    tools=[get_state_detail],
    sub_agents=[],  # Populated in agent.py after all sub-agents are defined
    before_agent_callback=ensure_tools_initialized,
)
