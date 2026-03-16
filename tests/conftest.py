"""Shared pytest configuration for Noor tests.

NOTE on Windows asyncio policy:
  Python 3.14+ on Windows uses ProactorEventLoop by default, which now works
  correctly with Playwright's subprocess management. The WindowsSelectorEventLoop
  does NOT support subprocess creation and will fail with Playwright.
  We only override to SelectorEventLoop on Python < 3.14 where ProactorEventLoop
  had pipe-handling bugs that affected Playwright.
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv()  # Load .env so GOOGLE_API_KEY / GOOGLE_CLOUD_PROJECT are available

import pytest
from google.genai import types

from noor_agent.agent import root_agent
from noor_agent.browser.manager import BrowserManager


# ---------------------------------------------------------------------------
# Browser fixture (integration tests)
# ---------------------------------------------------------------------------


@pytest.fixture
async def browser():
    """Provide a started BrowserManager for tests.

    Uses the same multi-strategy launch as production:
    - Set NOOR_BROWSER_CHANNEL=msedge in your .env for Windows
    - Leave unset in CI/Docker for bundled Chromium
    """
    bm = BrowserManager(headless=True)
    await bm.start()
    yield bm
    await bm.stop()


# ---------------------------------------------------------------------------
# InMemoryRunner fixtures (agent-level tests)
# ---------------------------------------------------------------------------


_has_api_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CLOUD_PROJECT"))


@pytest.fixture
async def runner(browser):
    """Provide an InMemoryRunner with tool dependencies initialized."""
    from google.adk.runners import InMemoryRunner

    from noor_agent.browser.service import BrowserService
    from noor_agent.plugins import get_plugins
    from noor_agent.tools import browser_tools, page_tools, vision_tools
    from noor_agent.vision.analyzer import ScreenAnalyzer

    # Create a BrowserService wrapper around the test browser fixture
    service = BrowserService()
    service._manager = browser
    service._analyzer = ScreenAnalyzer()

    # Inject service into tool modules
    browser_tools.set_browser_service(service)
    vision_tools.set_browser_service(service)
    page_tools.set_browser_service(service)

    # Mark callback as initialized to skip re-init
    from noor_agent import callbacks
    callbacks._initialized = True

    return InMemoryRunner(
        agent=root_agent,
        app_name="noor-test",
        plugins=get_plugins(),
    )


@pytest.fixture
async def session(runner):
    """Provide a fresh session for each test."""
    return await runner.session_service.create_session(
        app_name="noor-test",
        user_id="test-user",
    )


# ---------------------------------------------------------------------------
# Helper functions for agent tests
# ---------------------------------------------------------------------------


async def ask_noor(runner, session, text: str) -> list:
    """Send a message to Noor and collect all events."""
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=text)],
    )
    events = []
    async for event in runner.run_async(
        user_id="test-user",
        session_id=session.id,
        new_message=content,
    ):
        events.append(event)
    return events


def get_final_text(events: list) -> str:
    """Extract the final text response from events."""
    for event in reversed(events):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    return part.text
    return ""


def get_tool_calls(events: list) -> list[str]:
    """Extract tool names that were called during the interaction."""
    tools = []
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    tools.append(part.function_call.name)
    return tools
