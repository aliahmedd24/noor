"""NoorOrchestrator — root LLM agent that delegates to sub-agents."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

from src.agents.callbacks import ensure_tools_initialized

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "orchestrator.txt").read_text()

orchestrator_agent = LlmAgent(
    name="NoorOrchestrator",
    model="gemini-2.5-flash",
    description=(
        "Noor is the main conversational agent — a warm, patient AI assistant "
        "for visually impaired users navigating the web. Noor manages the "
        "conversation, understands what the user wants to do, and coordinates "
        "with specialist agents to analyze screens, navigate websites, and "
        "read content aloud. Noor always narrates what is happening."
    ),
    instruction=_INSTRUCTIONS,
    output_key="orchestrator_output",
    sub_agents=[],  # Populated in agent.py after all sub-agents are defined
    before_agent_callback=ensure_tools_initialized,
)
