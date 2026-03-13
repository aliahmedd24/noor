"""Shared pytest configuration for Noor tests.

NOTE on Windows asyncio policy:
  Python 3.14+ on Windows uses ProactorEventLoop by default, which now works
  correctly with Playwright's subprocess management. The WindowsSelectorEventLoop
  does NOT support subprocess creation and will fail with Playwright.
  We only override to SelectorEventLoop on Python < 3.14 where ProactorEventLoop
  had pipe-handling bugs that affected Playwright.
"""

from __future__ import annotations

import sys

if sys.platform == "win32":
    import asyncio
    if sys.version_info < (3, 14):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest

from src.browser.manager import BrowserManager


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
