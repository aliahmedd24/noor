"""PageSummarizerAgent — content extraction and article reading."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "summarizer.txt").read_text()

summarizer_agent = LlmAgent(
    name="PageSummarizerAgent",
    model="gemini-2.5-flash",
    description=(
        "Specialist agent for reading and summarizing web page content. Extracts "
        "the main text, article body, search results, or product details from "
        "the current page and presents them in a clear, concise format suitable "
        "for reading aloud. Use this agent when the user wants to KNOW what a "
        "page says — reading articles, reviewing search results, or understanding "
        "form content."
    ),
    instruction=_INSTRUCTIONS,
    output_key="page_summary",
    tools=[],  # Populated in agent.py
)
