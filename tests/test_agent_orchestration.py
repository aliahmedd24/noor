"""Tests for ADK agent orchestration.

Tests cover:
- Agent hierarchy assembly (root_agent, sub-agents, tools)
- Agent definitions (name, model, description, output_key)
- Session state key configuration
- Tool wiring (each sub-agent has the correct tools)
- Instruction loading (prompts loaded from .txt files)
"""

from __future__ import annotations

import pytest

from src.agents.agent import root_agent
from src.agents.orchestrator import orchestrator_agent
from src.agents.vision_agent import vision_agent
from src.agents.navigator_agent import navigator_agent
from src.agents.summarizer_agent import summarizer_agent


# ---------------------------------------------------------------------------
# Agent hierarchy tests
# ---------------------------------------------------------------------------


class TestAgentHierarchy:
    """Verify the multi-agent tree is assembled correctly."""

    def test_root_agent_is_orchestrator(self):
        assert root_agent is orchestrator_agent

    def test_orchestrator_has_three_sub_agents(self):
        assert len(orchestrator_agent.sub_agents) == 3

    def test_sub_agents_are_correct_instances(self):
        names = {a.name for a in orchestrator_agent.sub_agents}
        assert names == {"ScreenVisionAgent", "NavigatorAgent", "PageSummarizerAgent"}

    def test_sub_agent_order(self):
        """Sub-agents should be ordered: vision, navigator, summarizer."""
        agents = orchestrator_agent.sub_agents
        assert agents[0].name == "ScreenVisionAgent"
        assert agents[1].name == "NavigatorAgent"
        assert agents[2].name == "PageSummarizerAgent"


# ---------------------------------------------------------------------------
# Agent definition tests
# ---------------------------------------------------------------------------


class TestAgentDefinitions:
    """Verify each agent has correct name, model, description, and output_key."""

    def test_orchestrator_name(self):
        assert orchestrator_agent.name == "NoorOrchestrator"

    def test_orchestrator_model(self):
        assert orchestrator_agent.model == "gemini-2.5-flash"

    def test_orchestrator_description_not_empty(self):
        assert len(orchestrator_agent.description) > 50

    def test_orchestrator_output_key(self):
        assert orchestrator_agent.output_key == "orchestrator_output"

    def test_vision_agent_name(self):
        assert vision_agent.name == "ScreenVisionAgent"

    def test_vision_agent_model(self):
        assert vision_agent.model == "gemini-2.5-flash"

    def test_vision_agent_output_key(self):
        assert vision_agent.output_key == "vision_analysis"

    def test_navigator_agent_name(self):
        assert navigator_agent.name == "NavigatorAgent"

    def test_navigator_agent_model(self):
        assert navigator_agent.model == "gemini-2.5-flash"

    def test_navigator_agent_output_key(self):
        assert navigator_agent.output_key == "navigation_result"

    def test_summarizer_agent_name(self):
        assert summarizer_agent.name == "PageSummarizerAgent"

    def test_summarizer_agent_model(self):
        assert summarizer_agent.model == "gemini-2.5-flash"

    def test_summarizer_agent_output_key(self):
        assert summarizer_agent.output_key == "page_summary"


# ---------------------------------------------------------------------------
# Tool wiring tests
# ---------------------------------------------------------------------------


class TestToolWiring:
    """Verify each sub-agent has the correct tools assigned."""

    def _tool_names(self, agent) -> set[str]:
        return {t.__name__ for t in agent.tools}

    def test_vision_agent_tools(self):
        names = self._tool_names(vision_agent)
        assert "analyze_current_page" in names
        assert "describe_page_aloud" in names
        assert "find_and_click" in names

    def test_navigator_agent_tools(self):
        names = self._tool_names(navigator_agent)
        expected = {
            "navigate_to_url",
            "click_at_coordinates",
            "click_element_by_text",
            "type_into_field",
            "scroll_down",
            "scroll_up",
            "press_enter",
            "press_tab",
            "go_back_in_browser",
            "take_screenshot_of_page",
            "get_current_page_url",
        }
        assert expected.issubset(names)

    def test_summarizer_agent_tools(self):
        names = self._tool_names(summarizer_agent)
        assert "analyze_current_page" in names
        assert "describe_page_aloud" in names
        assert "scroll_down" in names
        assert "extract_page_text" in names
        assert "get_page_metadata" in names

    def test_orchestrator_has_no_direct_tools(self):
        # Orchestrator delegates to sub-agents, should not have tools
        assert len(orchestrator_agent.tools) == 0


# ---------------------------------------------------------------------------
# Instruction prompt tests
# ---------------------------------------------------------------------------


class TestInstructionPrompts:
    """Verify instruction prompts are loaded and contain expected content."""

    def test_orchestrator_instruction_loaded(self):
        assert orchestrator_agent.instruction is not None
        assert len(orchestrator_agent.instruction) > 100

    def test_orchestrator_mentions_noor(self):
        assert "Noor" in orchestrator_agent.instruction

    def test_orchestrator_references_sub_agents(self):
        text = orchestrator_agent.instruction
        assert "ScreenVisionAgent" in text
        assert "NavigatorAgent" in text
        assert "PageSummarizerAgent" in text

    def test_orchestrator_references_session_state(self):
        text = orchestrator_agent.instruction
        assert "{vision_analysis}" in text
        assert "{navigation_result}" in text
        assert "{page_summary}" in text

    def test_vision_instruction_loaded(self):
        assert vision_agent.instruction is not None
        assert "screenshot" in vision_agent.instruction.lower()

    def test_vision_references_viewport(self):
        text = vision_agent.instruction
        assert "1280" in text
        assert "800" in text

    def test_navigator_instruction_loaded(self):
        assert navigator_agent.instruction is not None
        assert "browser" in navigator_agent.instruction.lower()

    def test_navigator_references_vision_state(self):
        assert "{vision_analysis}" in navigator_agent.instruction

    def test_summarizer_instruction_loaded(self):
        assert summarizer_agent.instruction is not None
        assert "summarize" in summarizer_agent.instruction.lower() or "summary" in summarizer_agent.instruction.lower()

    def test_summarizer_handles_page_types(self):
        text = summarizer_agent.instruction.lower()
        # Should handle at least articles and search results
        assert "article" in text
        assert "search" in text


# ---------------------------------------------------------------------------
# Session state key tests
# ---------------------------------------------------------------------------


class TestSessionStateKeys:
    """Verify output_key values match the session state schema in CLAUDE.md."""

    def test_vision_output_key_is_vision_analysis(self):
        assert vision_agent.output_key == "vision_analysis"

    def test_navigator_output_key_is_navigation_result(self):
        assert navigator_agent.output_key == "navigation_result"

    def test_summarizer_output_key_is_page_summary(self):
        assert summarizer_agent.output_key == "page_summary"


# ---------------------------------------------------------------------------
# Callback tests
# ---------------------------------------------------------------------------


class TestCallbacks:
    """Verify the before_agent_callback is wired for tool initialization."""

    def test_orchestrator_has_before_agent_callback(self):
        assert orchestrator_agent.before_agent_callback is not None

    def test_callback_is_ensure_tools_initialized(self):
        from src.agents.callbacks import ensure_tools_initialized
        assert orchestrator_agent.before_agent_callback is ensure_tools_initialized


# ---------------------------------------------------------------------------
# ADK Runner integration tests (require API credentials)
# ---------------------------------------------------------------------------

import os

_has_api_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CLOUD_PROJECT"))
api = pytest.mark.skipif(not _has_api_key, reason="No Gemini API credentials available")


@api
class TestADKRunnerIntegration:
    """Integration tests that run the full agent pipeline with ADK Runner.

    These tests require either GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT
    environment variables to be set.
    """

    @pytest.fixture
    async def runner_and_session(self, browser):
        """Create an ADK Runner with a fresh session, tools initialized."""
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from src.tools import browser_tools, vision_tools, page_tools
        from src.vision.analyzer import ScreenAnalyzer

        # Inject browser and analyzer into tool modules
        browser_tools.set_browser_manager(browser)
        vision_tools.set_browser_manager(browser)
        vision_tools.set_screen_analyzer(ScreenAnalyzer())
        page_tools.set_browser_manager(browser)

        # Mark callback as initialized to skip re-init
        from src.agents import callbacks
        callbacks._initialized = True

        session_service = InMemorySessionService()
        runner = Runner(
            agent=root_agent,
            app_name="noor-test",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="noor-test",
            user_id="test-user",
        )
        yield runner, session

    async def _send_message(self, runner, session, text: str) -> str:
        """Send a text message to the agent and collect the response."""
        from google.genai import types

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text)],
        )
        parts = []
        async for event in runner.run(
            user_id="test-user",
            session_id=session.id,
            new_message=content,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        parts.append(part.text)
        return "\n".join(parts)

    async def test_navigate_to_google(self, runner_and_session):
        """Agent should navigate to Google when asked."""
        runner, session = runner_and_session
        response = await self._send_message(
            runner, session, "Go to google.com"
        )
        assert len(response) > 0
        # Response should mention Google or the page

    async def test_describe_page(self, runner_and_session):
        """Agent should describe the current page when asked."""
        runner, session = runner_and_session
        # First navigate somewhere
        await self._send_message(runner, session, "Go to google.com")
        response = await self._send_message(
            runner, session, "What's on the screen?"
        )
        assert len(response) > 0
