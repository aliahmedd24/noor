"""NoorOrchestrator — root LLM agent that delegates to sub-agents."""

from __future__ import annotations

from pathlib import Path

from google.adk.agents import LlmAgent

_INSTRUCTIONS = (Path(__file__).parent / "instructions" / "orchestrator.txt").read_text()

orchestrator_agent = LlmAgent(
    name="NoorOrchestrator",
    model="gemini-2.5-flash",
    description=(
        "Root orchestrator for Noor. Receives user voice requests, decides which "
        "sub-agent to delegate to, and narrates results back to the user."
    ),
    instruction=_INSTRUCTIONS,
    output_key="orchestrator_output",
    sub_agents=[],  # Populated in agent.py after all sub-agents are defined
)
