"""Agent lifecycle callbacks — initialization, validation, error handling, and state management.

This module provides all callback functions used across the Noor agent hierarchy:
- before_agent_callback: Lazy tool initialization + session state defaults
- before_tool_callback: Input validation for NavigatorAgent tools
- after_tool_callback: Error logging, state tracking, and error page detection
- Tool lifecycle events emitted via ``_ui_events`` session state queue for WebSocket.
"""

from __future__ import annotations

import os
import time

import structlog

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext

logger = structlog.get_logger(__name__)

_initialized = False


def _push_ui_event(state: dict, event: dict) -> None:
    """Append a UI event to the session state queue for WebSocket emission.

    The server's WebSocket endpoint drains ``_ui_events`` after each ADK event
    and forwards them to the client.
    """
    try:
        events = state.get("_ui_events", [])
        events.append(event)
        state["_ui_events"] = events
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Before-agent callback (root orchestrator)
# ---------------------------------------------------------------------------


async def ensure_tools_initialized(callback_context: CallbackContext) -> None:
    """Initialize browser and vision tool dependencies on first agent run.

    This callback is attached to the root orchestrator as a
    ``before_agent_callback``. On first invocation it:
    1. Creates and starts the BrowserService.
    2. Injects the service into all tool modules.
    3. Sets default session state values so template variables resolve.

    Args:
        callback_context: ADK CallbackContext for state access.

    Returns:
        None — returning None tells ADK to continue normal agent processing.
    """
    # Always ensure session state defaults exist (even on subsequent turns)
    _ensure_state_defaults(callback_context)

    global _initialized
    if _initialized:
        return None

    logger.info("initializing_tool_dependencies")

    from .browser.service import BrowserService, set_browser_service
    from .tools import browser_tools, vision_tools, page_tools

    # Read config from environment variables
    headless = os.getenv("NOOR_BROWSER_HEADLESS", "true").lower() == "true"
    channel = os.getenv("NOOR_BROWSER_CHANNEL") or None
    cdp_endpoint = os.getenv("NOOR_CDP_ENDPOINT") or None

    # Start browser service
    service = BrowserService()
    await service.start(
        headless=headless,
        channel=channel,
        cdp_endpoint=cdp_endpoint,
    )

    # Set module-level singleton
    set_browser_service(service)

    # Inject into tool modules
    browser_tools.set_browser_service(service)
    vision_tools.set_browser_service(service)
    page_tools.set_browser_service(service)

    _initialized = True
    logger.info(
        "tool_dependencies_initialized",
        browser_strategy=service.browser.launch_strategy,
    )
    return None


def _ensure_state_defaults(callback_context: CallbackContext) -> None:
    """Set default values for session state keys used in instruction templates.

    ADK substitutes ``{key}`` in agent instructions with ``state["key"]``.
    Without defaults, unresolved keys render as empty strings on the first
    turn before any tool has written to them.
    """
    defaults = {
        "vision_analysis": "(No page has been analyzed yet.)",
        "navigation_result": "(No navigation action taken yet.)",
        "page_summary": "(No page has been summarized yet.)",
        "current_url": "about:blank",
        "current_title": "(no page loaded)",
        "last_tool_error": "",
    }
    for key, default in defaults.items():
        callback_context.state.setdefault(key, default)


# ---------------------------------------------------------------------------
# Before-tool callback (NavigatorAgent input validation)
# ---------------------------------------------------------------------------


async def validate_navigator_tool_inputs(
    tool,
    args: dict,
    tool_context: ToolContext,
) -> dict | None:
    """Validate NavigatorAgent tool inputs before execution.

    Catches common errors like out-of-viewport coordinates or empty URLs
    before the tool runs, saving a round-trip to the browser.

    Returns:
        None to proceed with tool execution, or a dict to skip the tool
        and return the dict as the tool response.
    """
    tool_name = getattr(tool, "name", str(tool))

    # Validate URL for navigate_to_url
    if tool_name == "navigate_to_url":
        url = args.get("url", "")
        if not url or not url.strip():
            return {
                "status": "error",
                "error": "URL cannot be empty. Provide a full URL like https://www.google.com",
            }
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            # Auto-fix: prepend https://
            args["url"] = f"https://{url}"
            logger.info("auto_prepended_https", original=url, fixed=args["url"])

    # Validate coordinates for click_at_coordinates
    if tool_name == "click_at_coordinates":
        x = args.get("x", 0)
        y = args.get("y", 0)
        if not (0 <= x <= 1280):
            return {
                "status": "error",
                "error": f"x-coordinate {x} is outside the viewport (0–1280). "
                "Use analyze_current_page to get correct element coordinates.",
            }
        if not (0 <= y <= 800):
            return {
                "status": "error",
                "error": f"y-coordinate {y} is outside the viewport (0–800). "
                "Use analyze_current_page to get correct element coordinates.",
            }

    # Validate type_into_field text
    if tool_name == "type_into_field":
        text = args.get("text", "")
        if not text:
            return {
                "status": "error",
                "error": "Cannot type empty text. Provide the text to type.",
            }
        # Validate optional coordinates
        x = args.get("x", 0)
        y = args.get("y", 0)
        if (x != 0 or y != 0) and (not (0 <= x <= 1280) or not (0 <= y <= 800)):
            return {
                "status": "error",
                "error": f"Coordinates ({x}, {y}) are outside the viewport. "
                "Use 0,0 to skip coordinate-based focus, or provide valid coordinates.",
            }

    # Validate click_element_by_text
    if tool_name == "click_element_by_text":
        text = args.get("text", "")
        if not text or not text.strip():
            return {
                "status": "error",
                "error": "Element text cannot be empty. Describe the visible text of the element to click.",
            }

    # Emit tool_start UI event
    _push_ui_event(tool_context.state, {
        "type": "tool_start",
        "tool": tool_name,
        "args": {k: str(v)[:200] for k, v in args.items()},
    })

    # Track start time for duration calculation
    tool_context.state["_tool_start_time"] = time.monotonic()

    return None  # Proceed with tool execution


# ---------------------------------------------------------------------------
# Before-tool callback (generic — vision + summarizer agents)
# ---------------------------------------------------------------------------


async def emit_tool_start(
    tool,
    args: dict,
    tool_context: ToolContext,
) -> dict | None:
    """Emit a tool_start UI event for all sub-agent tools.

    Attached as ``before_tool_callback`` on ScreenVisionAgent and
    PageSummarizerAgent (NavigatorAgent uses its own validator which
    also emits tool_start).

    Returns:
        None — always proceeds with tool execution.
    """
    tool_name = getattr(tool, "name", str(tool))
    _push_ui_event(tool_context.state, {
        "type": "tool_start",
        "tool": tool_name,
        "args": {k: str(v)[:200] for k, v in args.items()},
    })
    tool_context.state["_tool_start_time"] = time.monotonic()
    return None


# ---------------------------------------------------------------------------
# After-tool callback (error logging — all sub-agents)
# ---------------------------------------------------------------------------


async def log_tool_errors(
    tool,
    args: dict,
    tool_context: ToolContext,
    tool_response: dict,
) -> dict | None:
    """Log tool errors, detect error pages, and record failure state.

    Attached as ``after_tool_callback`` on agents that use browser/vision tools.
    If a tool returns ``status: error``, logs the failure and sets a
    ``last_tool_error`` session state key so the orchestrator can react.

    Also detects error pages (404, 500, etc.) from navigation results
    and sets a ``_should_rewind`` flag for session rewind recovery.

    Returns:
        None to pass through the original tool_response unchanged.
    """
    if isinstance(tool_response, dict) and tool_response.get("status") == "error":
        error_msg = tool_response.get("error", "unknown error")
        logger.warning(
            "tool_returned_error",
            tool_name=getattr(tool, "name", str(tool)),
            error=error_msg,
            args=args,
        )
        try:
            tool_context.state["last_tool_error"] = error_msg
        except Exception:
            pass
    else:
        # Clear previous error on success
        try:
            tool_context.state["last_tool_error"] = ""
        except Exception:
            pass

    # Error page detection for session rewind
    if isinstance(tool_response, dict):
        title = str(tool_response.get("title", "")).lower()
        url = str(tool_response.get("url", ""))
        error_indicators = ["404", "not found", "error", "500", "403", "forbidden"]
        if any(ind in title for ind in error_indicators):
            try:
                tool_context.state["_should_rewind"] = True
                tool_context.state["_rewind_reason"] = f"Error page detected: {title}"
                logger.warning(
                    "error_page_detected",
                    title=title,
                    url=url,
                    tool_name=getattr(tool, "name", str(tool)),
                )
            except Exception:
                pass

    # Emit tool_end UI event
    tool_name = getattr(tool, "name", str(tool))
    status = "error" if isinstance(tool_response, dict) and tool_response.get("status") == "error" else "success"
    start_time = tool_context.state.get("_tool_start_time", 0)
    duration_ms = int((time.monotonic() - start_time) * 1000) if start_time else 0

    _push_ui_event(tool_context.state, {
        "type": "tool_end",
        "tool": tool_name,
        "status": status,
        "duration_ms": duration_ms,
    })

    # If tool was a screenshot/vision tool, emit screenshot event for the UI
    # and strip the base64 data from the response so it doesn't bloat the
    # LLM conversation context (~55K tokens per screenshot).
    screenshot_tools = {
        "take_screenshot_of_page",
        "analyze_current_page",
        "describe_page_aloud",
        "find_and_click",
    }
    needs_strip = False
    if tool_name in screenshot_tools and isinstance(tool_response, dict):
        screenshot_b64 = tool_response.get("screenshot_base64")
        if screenshot_b64:
            needs_strip = True
            annotations = tool_response.get("interactive_elements", [])
            _push_ui_event(tool_context.state, {
                "type": "screenshot",
                "data": screenshot_b64,
                "annotations": annotations[:20],
            })

    if needs_strip:
        # Return a cleaned copy without screenshot_base64 to keep LLM
        # context lean. The UI already received the screenshot via events.
        cleaned = {k: v for k, v in tool_response.items() if k != "screenshot_base64"}
        return cleaned

    return None
