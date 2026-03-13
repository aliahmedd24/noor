"""ScreenVisionAgent — screenshot analysis and element identification."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "vision.txt").read_text()

vision_agent = LlmAgent(
    name="ScreenVisionAgent",
    model="gemini-2.5-flash",
    description=(
        "Specialist agent for visual analysis of web pages. Captures screenshots "
        "and uses AI vision to understand page layout, identify interactive elements "
        "(buttons, links, forms, menus), describe images, and read text content. "
        "Use this agent when you need to SEE what is currently on the screen or "
        "find a specific element to interact with."
    ),
    instruction=_INSTRUCTIONS,
    output_key="vision_analysis",
    tools=[],  # Populated in agent.py
)
