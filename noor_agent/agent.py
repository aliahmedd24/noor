"""
Noor Agent — Root ADK agent definition with App-level runtime configuration.

This module assembles the multi-agent hierarchy, wraps it in an ADK ``App``
with context compaction and resumability, and exports the ``root_agent``
that ADK uses as the entry point for all interactions.

Architecture:
    NoorTaskLoop (LoopAgent, max_iterations=10)
    └── NoorOrchestrator (LlmAgent, BuiltInPlanner)
        ├── ScreenVisionAgent    (disallow_transfer_to_peers)
        ├── NavigatorAgent       (disallow_transfer_to_peers, before_tool_callback)
        └── PageSummarizerAgent  (disallow_transfer_to_peers)

The LoopAgent allows the orchestrator to chain multiple sub-agent
delegations per user request (e.g., navigate → vision → summarize).
The orchestrator calls task_complete() to escalate and stop the loop
when the user's request is fully handled.
"""

from google.adk.agents import LoopAgent
from google.adk.apps.app import App, EventsCompactionConfig, ResumabilityConfig

from .orchestrator import orchestrator_agent
from .plugins import get_plugins

# Wrap the orchestrator in a LoopAgent so it can chain multiple
# tool calls per user turn (navigate → analyze → narrate).
# The orchestrator calls task_complete() to break the loop.
task_loop = LoopAgent(
    name="NoorTaskLoop",
    description=(
        "Noor's task execution loop. Keeps the orchestrator running "
        "until the user's request is fully handled — navigating, analyzing, "
        "clicking, typing, and narrating across multiple steps."
    ),
    sub_agents=[orchestrator_agent],
    max_iterations=10,
)

# ADK convention: the framework discovers agents via this name
root_agent = task_loop

# App object — wraps root_agent with runtime configuration for:
# - Context compaction: summarizes older events to keep context manageable
#   during long web navigation sessions (many screenshots + tool calls).
# - Resumability: recovers from interruptions (Cloud Run cold starts,
#   WebSocket disconnects) without replaying the entire session.
app = App(
    name="noor",
    root_agent=root_agent,
    plugins=get_plugins(),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=5,  # Compact every 5 invocations
        overlap_size=1,         # Keep 1 prior event in the new context window
    ),
    resumability_config=ResumabilityConfig(
        is_resumable=True,
    ),
)
