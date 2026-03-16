"""
Noor Agent — Root ADK agent definition with App-level runtime configuration.

This module assembles the multi-agent hierarchy, wraps it in an ADK ``App``
with context compaction and resumability, and exports the ``root_agent``
that ADK uses as the entry point for all interactions.

Two root agents are produced:

* ``root_agent`` — text mode (``gemini-3.1-pro-preview``, BuiltInPlanner).
  Used by ``runner.run_async()`` in the text-only WebSocket endpoint.
* ``streaming_root_agent`` — voice mode (native-audio Live API model, no
  planner).  Used by ``runner.run_live()`` in the bidi-streaming endpoint.

Architecture (both variants share the same shape):
    NoorTaskLoop (LoopAgent, max_iterations=10)
    └── NoorOrchestrator (LlmAgent)

The LoopAgent allows the orchestrator to chain multiple tool calls per user
turn (navigate → analyze → narrate).  The orchestrator calls
``task_complete()`` to escalate and stop the loop when the user's request
is fully handled.
"""

import os
from functools import cached_property

from google.adk.agents import LoopAgent
from google.adk.models.google_llm import Gemini
from google.adk.apps.app import App, EventsCompactionConfig, ResumabilityConfig
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.genai import types as genai_types

from .orchestrator import orchestrator_agent, create_orchestrator
from .plugins import get_plugins

# ──────────────────────────────────────────────────────────────────
# Multi-region Gemini: text model on "global", Live API on regional
# ──────────────────────────────────────────────────────────────────

_LIVE_REGION = os.getenv("NOOR_LIVE_API_LOCATION", "us-central1")
_LIVE_MODEL_NAME = "gemini-live-2.5-flash-native-audio"


class _RegionalLiveGemini(Gemini):
    """Gemini variant that routes Live API calls to a regional endpoint.

    The text model (gemini-3.1-pro) only works on ``global``, but the
    Live API (native audio) requires a regional endpoint like ``us-central1``.
    This subclass overrides ``_live_api_client`` to create a Vertex AI Client
    pinned to the regional endpoint while leaving the text client untouched.
    """

    live_location: str = "us-central1"

    @cached_property
    def _live_api_client(self):
        from google.genai import Client

        return Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=self.live_location,
            http_options=genai_types.HttpOptions(
                headers=self._tracking_headers(),
                api_version=self._live_api_version,
            ),
        )


# Build the Live API model instance with regional routing
LIVE_MODEL = _RegionalLiveGemini(
    model=_LIVE_MODEL_NAME,
    live_location=_LIVE_REGION,
)

_LOOP_DESCRIPTION = (
    "Noor's task execution loop. Keeps the orchestrator running "
    "until the user's request is fully handled — navigating, analyzing, "
    "clicking, typing, and narrating across multiple steps."
)

# ──────────────────────────────────────────────────────────────────
# Text-mode root agent (default — used by adk run / adk web / text WS)
# ──────────────────────────────────────────────────────────────────

task_loop = LoopAgent(
    name="NoorTaskLoop",
    description=_LOOP_DESCRIPTION,
    sub_agents=[orchestrator_agent],
    max_iterations=10,
)

# ADK convention: the framework discovers agents via this name
root_agent = task_loop

# ──────────────────────────────────────────────────────────────────
# Streaming-mode root agent (Live API native audio)
# ──────────────────────────────────────────────────────────────────

# Live API does NOT support LoopAgent — use the LlmAgent directly.
# The orchestrator's tool set + task_complete() handle multi-step flows.
streaming_root_agent = create_orchestrator(
    model=LIVE_MODEL,
    use_planner=False,  # native-audio models don't support extended thinking
)

# ──────────────────────────────────────────────────────────────────
# App object (wraps the text-mode root agent)
# ──────────────────────────────────────────────────────────────────

app = App(
    name="noor",
    root_agent=root_agent,
    plugins=get_plugins(),
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=5,
        overlap_size=1,
        summarizer=LlmEventSummarizer(llm=orchestrator_agent.canonical_model),
    ),
    resumability_config=ResumabilityConfig(
        is_resumable=True,
    ),
)
