"""NavigatorAgent — browser action planning and execution."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "navigator.txt").read_text()

navigator_agent = LlmAgent(
    name="NavigatorAgent",
    model="gemini-2.5-flash",
    description=(
        "Plans and executes browser actions such as clicking elements, typing text, "
        "scrolling, and navigating to URLs. Uses the latest vision analysis from "
        "ScreenVisionAgent to decide where and how to act."
    ),
    instruction=_INSTRUCTIONS,
    output_key="navigation_result",
    tools=[],  # Populated in agent.py
)
