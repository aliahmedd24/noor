"""Tests for ADK agent orchestration.

Tests cover:
- Agent hierarchy assembly (root_agent, sub-agents, tools)
- Agent definitions (name, model, description, output_key, output_schema)
- BuiltInPlanner on orchestrator
- Session state key configuration
- Tool wiring (each sub-agent has the correct tools)
- Instruction loading (prompts from prompts.py)
- Callbacks (before_agent, before_tool, after_tool)
- App object (compaction, resumability, plugins)
"""

from __future__ import annotations

import pytest

from noor_agent.agent import root_agent, app
from noor_agent.orchestrator import orchestrator_agent
from noor_agent.vision_agent import vision_agent
from noor_agent.navigator_agent import navigator_agent
from noor_agent.summarizer_agent import summarizer_agent


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
    """Verify each agent has correct name, model, description, output_key, and output_schema."""

    def test_orchestrator_name(self):
        assert orchestrator_agent.name == "NoorOrchestrator"

    def test_orchestrator_model(self):
        assert orchestrator_agent.model == "gemini-3.1-pro-preview"

    def test_orchestrator_description_not_empty(self):
        assert len(orchestrator_agent.description) > 50

    def test_orchestrator_output_key(self):
        assert orchestrator_agent.output_key == "orchestrator_output"

    def test_orchestrator_has_builtin_planner(self):
        from google.adk.planners import BuiltInPlanner
        assert isinstance(orchestrator_agent.planner, BuiltInPlanner)

    def test_orchestrator_planner_thinking_budget(self):
        planner = orchestrator_agent.planner
        assert planner.thinking_config.thinking_budget == 2048

    def test_orchestrator_planner_includes_thoughts(self):
        planner = orchestrator_agent.planner
        assert planner.thinking_config.include_thoughts is True

    def test_orchestrator_temperature(self):
        assert orchestrator_agent.generate_content_config is not None
        assert orchestrator_agent.generate_content_config.temperature == 0.3

    def test_vision_agent_name(self):
        assert vision_agent.name == "ScreenVisionAgent"

    def test_vision_agent_model(self):
        assert vision_agent.model == "gemini-3.1-pro-preview"

    def test_vision_agent_output_key(self):
        assert vision_agent.output_key == "vision_analysis"

    def test_vision_agent_output_schema(self):
        from noor_agent.schemas import VisionOutput
        assert vision_agent.output_schema == VisionOutput

    def test_vision_agent_temperature(self):
        assert vision_agent.generate_content_config.temperature == 0.2

    def test_vision_agent_thinking_level(self):
        cfg = vision_agent.generate_content_config
        assert cfg.thinking_config is not None
        assert cfg.thinking_config.thinking_level == "LOW"

    def test_navigator_agent_name(self):
        assert navigator_agent.name == "NavigatorAgent"

    def test_navigator_agent_model(self):
        assert navigator_agent.model == "gemini-3.1-pro-preview"

    def test_navigator_agent_output_key(self):
        assert navigator_agent.output_key == "navigation_result"

    def test_navigator_agent_output_schema(self):
        from noor_agent.schemas import NavigationOutput
        assert navigator_agent.output_schema == NavigationOutput

    def test_navigator_agent_temperature(self):
        assert navigator_agent.generate_content_config.temperature == 0.1

    def test_navigator_agent_thinking_level(self):
        cfg = navigator_agent.generate_content_config
        assert cfg.thinking_config is not None
        assert cfg.thinking_config.thinking_level == "LOW"

    def test_summarizer_agent_name(self):
        assert summarizer_agent.name == "PageSummarizerAgent"

    def test_summarizer_agent_model(self):
        assert summarizer_agent.model == "gemini-3.1-pro-preview"

    def test_summarizer_agent_output_key(self):
        assert summarizer_agent.output_key == "page_summary"

    def test_summarizer_agent_output_schema(self):
        from noor_agent.schemas import SummaryOutput
        assert summarizer_agent.output_schema == SummaryOutput

    def test_summarizer_agent_thinking_level(self):
        cfg = summarizer_agent.generate_content_config
        assert cfg.thinking_config is not None
        assert cfg.thinking_config.thinking_level == "LOW"


# ---------------------------------------------------------------------------
# Peer transfer restriction tests
# ---------------------------------------------------------------------------


class TestPeerTransferRestrictions:
    """Verify sub-agents cannot transfer to peers (supervisor pattern)."""

    def test_vision_agent_disallows_peer_transfer(self):
        assert vision_agent.disallow_transfer_to_peers is True

    def test_navigator_agent_disallows_peer_transfer(self):
        assert navigator_agent.disallow_transfer_to_peers is True

    def test_summarizer_agent_disallows_peer_transfer(self):
        assert summarizer_agent.disallow_transfer_to_peers is True


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
        assert "take_screenshot_of_page" in names
        assert "get_current_page_url" in names

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
        }
        assert expected.issubset(names)

    def test_navigator_agent_tool_count_under_limit(self):
        """NavigatorAgent should have <=9 tools (split guideline)."""
        assert len(navigator_agent.tools) <= 9

    def test_summarizer_agent_tools(self):
        names = self._tool_names(summarizer_agent)
        assert "analyze_current_page" in names
        assert "describe_page_aloud" in names
        assert "scroll_down" in names
        assert "extract_page_text" in names
        assert "get_page_metadata" in names

    def test_orchestrator_has_state_detail_tool(self):
        assert len(orchestrator_agent.tools) == 1
        assert orchestrator_agent.tools[0].__name__ == "get_state_detail"


# ---------------------------------------------------------------------------
# Instruction prompt tests
# ---------------------------------------------------------------------------


class TestInstructionPrompts:
    """Verify instruction prompts are loaded and contain expected content."""

    def test_orchestrator_instruction_is_callable(self):
        assert callable(orchestrator_agent.instruction)

    def test_orchestrator_prompt_has_content(self):
        from noor_agent.prompts import ORCHESTRATOR_INSTRUCTION
        assert len(ORCHESTRATOR_INSTRUCTION) > 100

    def test_orchestrator_prompt_mentions_noor(self):
        from noor_agent.prompts import ORCHESTRATOR_INSTRUCTION
        assert "Noor" in ORCHESTRATOR_INSTRUCTION

    def test_orchestrator_prompt_references_delegation(self):
        from noor_agent.prompts import ORCHESTRATOR_INSTRUCTION
        assert "Vision specialist" in ORCHESTRATOR_INSTRUCTION
        assert "Navigation specialist" in ORCHESTRATOR_INSTRUCTION
        assert "Summarization specialist" in ORCHESTRATOR_INSTRUCTION

    def test_orchestrator_prompt_references_session_state(self):
        from noor_agent.prompts import ORCHESTRATOR_INSTRUCTION
        assert "{vision_analysis}" in ORCHESTRATOR_INSTRUCTION
        assert "{navigation_result}" in ORCHESTRATOR_INSTRUCTION
        assert "{page_summary}" in ORCHESTRATOR_INSTRUCTION

    def test_orchestrator_prompt_references_error_handling(self):
        from noor_agent.prompts import ORCHESTRATOR_INSTRUCTION
        assert "{last_tool_error}" in ORCHESTRATOR_INSTRUCTION

    def test_vision_instruction_is_callable(self):
        assert callable(vision_agent.instruction)

    def test_vision_prompt_has_screenshot(self):
        from noor_agent.prompts import VISION_INSTRUCTION
        assert "screenshot" in VISION_INSTRUCTION.lower()

    def test_vision_prompt_references_viewport(self):
        from noor_agent.prompts import VISION_INSTRUCTION
        assert "1280" in VISION_INSTRUCTION
        assert "800" in VISION_INSTRUCTION

    def test_vision_prompt_has_reasoning_steps(self):
        from noor_agent.prompts import VISION_INSTRUCTION
        assert "Capture" in VISION_INSTRUCTION
        assert "Interpret" in VISION_INSTRUCTION
        assert "Report" in VISION_INSTRUCTION

    def test_navigator_instruction_is_callable(self):
        assert callable(navigator_agent.instruction)

    def test_navigator_prompt_has_browser(self):
        from noor_agent.prompts import NAVIGATOR_INSTRUCTION
        assert "browser" in NAVIGATOR_INSTRUCTION.lower()

    def test_navigator_prompt_references_vision_state(self):
        from noor_agent.prompts import NAVIGATOR_INSTRUCTION
        assert "{vision_analysis}" in NAVIGATOR_INSTRUCTION

    def test_navigator_prompt_has_reasoning_steps(self):
        from noor_agent.prompts import NAVIGATOR_INSTRUCTION
        assert "Analyze" in NAVIGATOR_INSTRUCTION
        assert "Plan" in NAVIGATOR_INSTRUCTION
        assert "Execute" in NAVIGATOR_INSTRUCTION
        assert "Verify" in NAVIGATOR_INSTRUCTION

    def test_summarizer_instruction_is_callable(self):
        assert callable(summarizer_agent.instruction)

    def test_summarizer_prompt_has_summary(self):
        from noor_agent.prompts import SUMMARIZER_INSTRUCTION
        assert "summarize" in SUMMARIZER_INSTRUCTION.lower() or "summary" in SUMMARIZER_INSTRUCTION.lower()

    def test_summarizer_prompt_handles_page_types(self):
        from noor_agent.prompts import SUMMARIZER_INSTRUCTION
        text = SUMMARIZER_INSTRUCTION.lower()
        assert "article" in text
        assert "search" in text
        assert "form" in text
        assert "product" in text


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
    """Verify callbacks are wired correctly."""

    def test_orchestrator_has_before_agent_callback(self):
        assert orchestrator_agent.before_agent_callback is not None

    def test_callback_is_ensure_tools_initialized(self):
        from noor_agent.callbacks import ensure_tools_initialized
        assert orchestrator_agent.before_agent_callback is ensure_tools_initialized

    def test_vision_agent_has_after_tool_callback(self):
        from noor_agent.callbacks import log_tool_errors
        assert vision_agent.after_tool_callback is log_tool_errors

    def test_navigator_agent_has_before_tool_callback(self):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        assert navigator_agent.before_tool_callback is validate_navigator_tool_inputs

    def test_navigator_agent_has_after_tool_callback(self):
        from noor_agent.callbacks import log_tool_errors
        assert navigator_agent.after_tool_callback is log_tool_errors

    def test_summarizer_agent_has_after_tool_callback(self):
        from noor_agent.callbacks import log_tool_errors
        assert summarizer_agent.after_tool_callback is log_tool_errors


# ---------------------------------------------------------------------------
# App object tests
# ---------------------------------------------------------------------------


class TestAppObject:
    """Verify the ADK App is configured with compaction and resumability."""

    def test_app_exists(self):
        assert app is not None

    def test_app_name(self):
        assert app.name == "noor"

    def test_app_root_agent_is_orchestrator(self):
        assert app.root_agent is orchestrator_agent

    def test_app_has_compaction_config(self):
        assert app.events_compaction_config is not None
        assert app.events_compaction_config.compaction_interval == 5
        assert app.events_compaction_config.overlap_size == 1

    def test_app_has_resumability_config(self):
        assert app.resumability_config is not None
        assert app.resumability_config.is_resumable is True

    def test_app_has_plugins(self):
        assert app.plugins is not None
        assert len(app.plugins) >= 2  # ReflectAndRetry + Logging


# ---------------------------------------------------------------------------
# Plugin tests
# ---------------------------------------------------------------------------


class TestPlugins:
    """Verify plugins are configured correctly."""

    def test_get_plugins_returns_list(self):
        from noor_agent.plugins import get_plugins
        plugins = get_plugins()
        assert isinstance(plugins, list)
        assert len(plugins) >= 2

    def test_reflect_and_retry_plugin_present(self):
        from noor_agent.plugins import get_plugins
        from google.adk.plugins import ReflectAndRetryToolPlugin
        plugins = get_plugins()
        retry_plugins = [p for p in plugins if isinstance(p, ReflectAndRetryToolPlugin)]
        assert len(retry_plugins) == 1

    def test_logging_plugin_present(self):
        from noor_agent.plugins import get_plugins
        from google.adk.plugins import LoggingPlugin, DebugLoggingPlugin
        plugins = get_plugins()
        log_plugins = [p for p in plugins if isinstance(p, (LoggingPlugin, DebugLoggingPlugin))]
        assert len(log_plugins) == 1


# ---------------------------------------------------------------------------
# Callback logic tests (unit tests for validation)
# ---------------------------------------------------------------------------


class TestValidateNavigatorToolInputs:
    """Unit tests for the before_tool_callback validation logic."""

    @pytest.fixture
    def mock_tool(self):
        class FakeTool:
            def __init__(self, name):
                self.name = name
        return FakeTool

    @pytest.fixture
    def mock_tool_context(self):
        class FakeToolContext:
            def __init__(self):
                self.state = {}
        return FakeToolContext()

    async def test_rejects_empty_url(self, mock_tool, mock_tool_context):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        tool = mock_tool("navigate_to_url")
        result = await validate_navigator_tool_inputs(tool, {"url": ""}, mock_tool_context)
        assert result is not None
        assert result["status"] == "error"

    async def test_auto_prepends_https(self, mock_tool, mock_tool_context):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        tool = mock_tool("navigate_to_url")
        args = {"url": "www.google.com"}
        result = await validate_navigator_tool_inputs(tool, args, mock_tool_context)
        assert result is None  # Proceed — URL was fixed in-place
        assert args["url"] == "https://www.google.com"

    async def test_rejects_out_of_bounds_x(self, mock_tool, mock_tool_context):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        tool = mock_tool("find_and_click")
        result = await validate_navigator_tool_inputs(tool, {"target_description": "btn", "x": 1500, "y": 400}, mock_tool_context)
        assert result is not None
        assert result["status"] == "error"

    async def test_rejects_out_of_bounds_y(self, mock_tool, mock_tool_context):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        tool = mock_tool("find_and_click")
        result = await validate_navigator_tool_inputs(tool, {"target_description": "btn", "x": 640, "y": 900}, mock_tool_context)
        assert result is not None
        assert result["status"] == "error"

    async def test_accepts_valid_coordinates(self, mock_tool, mock_tool_context):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        tool = mock_tool("find_and_click")
        result = await validate_navigator_tool_inputs(tool, {"target_description": "btn", "x": 640, "y": 400}, mock_tool_context)
        assert result is None  # Proceed

    async def test_rejects_empty_type_text(self, mock_tool, mock_tool_context):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        tool = mock_tool("type_into_field")
        result = await validate_navigator_tool_inputs(tool, {"text": ""}, mock_tool_context)
        assert result is not None
        assert result["status"] == "error"

    async def test_rejects_empty_click_text(self, mock_tool, mock_tool_context):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        tool = mock_tool("click_element_by_text")
        result = await validate_navigator_tool_inputs(tool, {"text": "  "}, mock_tool_context)
        assert result is not None
        assert result["status"] == "error"

    async def test_passes_unknown_tool(self, mock_tool, mock_tool_context):
        from noor_agent.callbacks import validate_navigator_tool_inputs
        tool = mock_tool("some_other_tool")
        result = await validate_navigator_tool_inputs(tool, {"x": 9999}, mock_tool_context)
        assert result is None  # No validation for unknown tools


# ---------------------------------------------------------------------------
# State helpers tests
# ---------------------------------------------------------------------------


class TestStateHelpers:
    """Tests for the minify_state helper."""

    def test_minify_state_truncates_long_values(self):
        from noor_agent.state_helpers import minify_state
        state = {"vision_analysis": "x" * 500, "current_url": "https://example.com"}
        result = minify_state(state, max_chars=200)
        assert len(result["vision_analysis"]) < 500
        assert "get_state_detail" in result["vision_analysis"]
        assert result["current_url"] == "https://example.com"

    def test_minify_state_preserves_short_values(self):
        from noor_agent.state_helpers import minify_state
        state = {"vision_analysis": "short", "current_url": "https://example.com"}
        result = minify_state(state, max_chars=200)
        assert result["vision_analysis"] == "short"

    def test_minify_state_defaults_missing_keys(self):
        from noor_agent.state_helpers import minify_state
        result = minify_state({})
        assert result["current_url"] == ""
        assert result["vision_analysis"] == ""


# ---------------------------------------------------------------------------
# State tools tests
# ---------------------------------------------------------------------------


class TestGetStateDetail:
    """Tests for the get_state_detail tool."""

    @pytest.fixture
    def mock_tool_context(self):
        class FakeToolContext:
            def __init__(self):
                self.state = {
                    "vision_analysis": "full detailed analysis here",
                    "current_url": "https://example.com",
                }
        return FakeToolContext()

    async def test_retrieves_valid_key(self, mock_tool_context):
        from noor_agent.tools.state_tools import get_state_detail
        result = await get_state_detail("vision_analysis", mock_tool_context)
        assert result["status"] == "success"
        assert result["value"] == "full detailed analysis here"

    async def test_rejects_invalid_key(self, mock_tool_context):
        from noor_agent.tools.state_tools import get_state_detail
        result = await get_state_detail("invalid_key", mock_tool_context)
        assert result["status"] == "error"

    async def test_returns_empty_for_missing_key(self, mock_tool_context):
        from noor_agent.tools.state_tools import get_state_detail
        result = await get_state_detail("page_summary", mock_tool_context)
        assert result["status"] == "success"
        assert result["value"] == ""


# NOTE: InMemoryRunner integration tests are in tests/test_agents.py
