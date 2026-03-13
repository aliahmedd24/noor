"""PageSummarizerAgent — content extraction and article reading."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "summarizer.txt").read_text()

summarizer_agent = LlmAgent(
    name="PageSummarizerAgent",
    model="gemini-2.5-flash",
    description=(
        "Extracts and summarizes page content for the user. Reads articles, "
        "describes search results, summarizes long pages, and presents content "
        "in a clear, spoken format suitable for audio delivery."
    ),
    instruction=_INSTRUCTIONS,
    output_key="page_summary",
    tools=[],  # Populated in agent.py
)
