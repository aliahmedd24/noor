"""
Noor Agent — Root ADK agent definition with App-level runtime configuration.

This module assembles the multi-agent hierarchy, wraps it in an ADK ``App``
with context compaction and resumability, and exports the ``root_agent``
that ADK uses as the entry point for all interactions.

Architecture:
    NoorOrchestrator (root)
    ├── ScreenVisionAgent    (disallow_transfer_to_peers)
    ├── NavigatorAgent       (disallow_transfer_to_peers, before_tool_callback)
    └── PageSummarizerAgent  (disallow_transfer_to_peers)
"""

from google.adk.apps.app import App, EventsCompactionConfig, ResumabilityConfig

from src.agents.orchestrator import orchestrator_agent
from src.agents.vision_agent import vision_agent
from src.agents.navigator_agent import navigator_agent
from src.agents.summarizer_agent import summarizer_agent
from src.agents.plugins import get_plugins

# Wire sub-agents into the orchestrator
orchestrator_agent.sub_agents = [
    vision_agent,
    navigator_agent,
    summarizer_agent,
]

# ADK convention: the framework discovers agents via this name
root_agent = orchestrator_agent

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
