"""Agent lifecycle callbacks — initialization, validation, error handling, and state management.

This module provides all callback functions used across the Noor agent hierarchy:
- before_agent_callback: Lazy tool initialization + session state defaults
- before_tool_callback: Input validation for NavigatorAgent tools
- after_tool_callback: Error logging, state tracking, and error page detection
"""

from __future__ import annotations

import structlog

from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext

logger = structlog.get_logger(__name__)

_initialized = False


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

    from src.config import settings
    from src.browser.service import BrowserService, set_browser_service
    from src.tools import browser_tools, vision_tools, page_tools

    # Start browser service
    headless = settings.noor_browser_headless
    channel = settings.noor_browser_channel or None
    cdp_endpoint = settings.noor_cdp_endpoint or None

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

    return None  # Proceed with tool execution


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

    # Phase 4: Error page detection for session rewind
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

    return None
