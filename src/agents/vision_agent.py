"""ScreenVisionAgent — screenshot analysis and element identification."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "vision.txt").read_text()

vision_agent = LlmAgent(
    name="ScreenVisionAgent",
    model="gemini-2.5-flash",
    description=(
        "Analyzes screenshots of the current browser page. Identifies interactive "
        "elements, reads text content, describes images, and reports the visual "
        "layout to help the user understand what is on screen."
    ),
    instruction=_INSTRUCTIONS,
    output_key="vision_analysis",
    tools=[],  # Populated in agent.py
)
