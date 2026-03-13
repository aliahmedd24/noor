"""NavigatorAgent — browser action planning and execution."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "navigator.txt").read_text()

navigator_agent = LlmAgent(
    name="NavigatorAgent",
    model="gemini-2.5-flash",
    description=(
        "Specialist agent for browser control and web navigation. Executes actions "
        "like clicking buttons, typing text, scrolling, navigating to URLs, and "
        "going back/forward. Use this agent when you need to INTERACT with the "
        "web page — clicking, typing, scrolling, or navigating to a new URL."
    ),
    instruction=_INSTRUCTIONS,
    output_key="navigation_result",
    tools=[],  # Populated in agent.py
)
