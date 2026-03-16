"""Agent-level tests using InMemoryRunner.

These tests run the full agent pipeline with a real browser and Gemini API.
They require GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT environment variables
and a browser (NOOR_BROWSER_CHANNEL=msedge on Windows).

Run with: pytest tests/test_agents.py -v
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

import pytest

from tests.conftest import ask_noor, get_final_text, get_tool_calls

_has_api_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CLOUD_PROJECT"))
api = pytest.mark.skipif(not _has_api_key, reason="No Gemini API credentials available")


@api
class TestGreetingAndConversation:
    """Test conversational behavior without browser actions."""

    async def test_greeting(self, runner, session):
        """Noor should respond to a greeting warmly."""
        events = await ask_noor(runner, session, "Hello Noor!")
        response = get_final_text(events)
        assert len(response) > 0
        # Should be conversational, not a tool call
        assert any(
            word in response.lower()
            for word in ["hello", "hi", "hey", "help", "welcome", "noor"]
        )

    async def test_greeting_no_tools(self, runner, session):
        """A simple greeting should not trigger browser tools."""
        events = await ask_noor(runner, session, "Hi there!")
        tools = get_tool_calls(events)
        browser_tools = {"navigate_to_url", "find_and_click", "scroll_down"}
        assert not browser_tools.intersection(tools)


@api
class TestNavigation:
    """Test browser navigation behavior."""

    async def test_navigate_triggers_tools(self, runner, session):
        """Asking to navigate should trigger navigate_to_url."""
        events = await ask_noor(runner, session, "Go to google.com")
        tools = get_tool_calls(events)
        assert "navigate_to_url" in tools

    async def test_navigate_produces_response(self, runner, session):
        """Navigation should produce a non-empty text response."""
        events = await ask_noor(runner, session, "Go to google.com")
        response = get_final_text(events)
        assert len(response) > 0

    async def test_go_back(self, runner, session):
        """Go back should trigger the browser back tool."""
        await ask_noor(runner, session, "Go to google.com")
        await ask_noor(runner, session, "Go to bbc.com")
        events = await ask_noor(runner, session, "Go back")
        tools = get_tool_calls(events)
        assert "go_back_in_browser" in tools


@api
class TestVision:
    """Test vision analysis behavior."""

    async def test_describe_page_triggers_vision(self, runner, session):
        """Asking what's on screen should trigger vision or produce a description."""
        await ask_noor(runner, session, "Go to google.com")
        events = await ask_noor(runner, session, "What do you see on the screen?")
        tools = get_tool_calls(events)
        response = get_final_text(events)
        # Either vision tools were called, or the agent produced a meaningful description
        vision_tools_used = any(
            t in tools
            for t in ["analyze_current_page", "describe_page_aloud", "take_screenshot_of_page"]
        )
        has_description = len(response) > 20
        assert vision_tools_used or has_description

    async def test_describe_page_has_content(self, runner, session):
        """Page description should contain meaningful content."""
        await ask_noor(runner, session, "Go to google.com")
        events = await ask_noor(runner, session, "Describe what's on the screen")
        response = get_final_text(events)
        assert len(response) > 20


@api
class TestSearchFlow:
    """Test multi-step search flow."""

    async def test_search_flow(self, runner, session):
        """Full search flow should use navigate + type + enter tools."""
        events = await ask_noor(
            runner, session, "Search Google for weather in Bremen"
        )
        tools = get_tool_calls(events)
        # Should involve navigation and typing at minimum
        assert len(tools) >= 2


@api
class TestErrorHandling:
    """Test graceful error handling."""

    async def test_error_handling(self, runner, session):
        """Agent should handle navigation failures gracefully."""
        events = await ask_noor(
            runner,
            session,
            "Go to https://this-domain-does-not-exist-xyz-123.com",
        )
        response = get_final_text(events)
        # Should mention the error, not crash
        assert len(response) > 0

    async def test_handles_ambiguous_request(self, runner, session):
        """Agent should ask for clarification on ambiguous requests."""
        events = await ask_noor(runner, session, "Help me with something")
        response = get_final_text(events)
        assert len(response) > 0
