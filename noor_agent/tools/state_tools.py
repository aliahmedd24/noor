"""Session state and flow control tools for Noor ADK agents.

Provides:
- get_state_detail: Retrieve full, untruncated state values
- task_complete: Signal that the user's request is fully handled (stops the loop)
"""

from __future__ import annotations

from google.adk.tools import ToolContext

_ALLOWED_KEYS = frozenset({
    "vision_analysis",
    "navigation_result",
    "page_summary",
    "current_url",
    "current_title",
    "last_tool_error",
})


async def get_state_detail(key: str, tool_context: ToolContext) -> dict:
    """Retrieve the full, untruncated value of a session state key.

    Use this when the summary in your instructions is insufficient and
    you need the complete data for a state key like vision_analysis,
    navigation_result, or page_summary.

    Args:
        key: The state key to retrieve (e.g., 'vision_analysis',
             'navigation_result', 'page_summary', 'current_url',
             'current_title', 'last_tool_error').

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - key: The requested key name
        - value: The full untruncated value, or empty string if not set
        - error: Error message if the key is not recognized
    """
    try:
        if key not in _ALLOWED_KEYS:
            return {
                "status": "error",
                "key": key,
                "value": "",
                "error": (
                    f"Unknown state key '{key}'. "
                    f"Allowed keys: {', '.join(sorted(_ALLOWED_KEYS))}"
                ),
            }
        value = str(tool_context.state.get(key, ""))
        return {
            "status": "success",
            "key": key,
            "value": value,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "key": key,
            "value": "",
            "error": str(e),
        }


async def explain_what_happened(tool_context: ToolContext) -> dict:
    """Explain the recent actions and their results to the user.

    Use this tool when the user asks 'what just happened?', 'why didn't
    that work?', 'what did you do?', or any question about recent actions.

    Reads the session state to build a plain-English explanation of the
    last actions taken, their results, and any errors that occurred.

    Args:
        tool_context: ADK tool context for session state access.

    Returns:
        A dictionary with:
        - status: 'success'
        - explanation: Human-readable summary of recent activity
        - recent_tools: List of recent tool names and outcomes
        - last_error: The most recent error, or empty string
        - current_url: Where the browser is now
        - current_title: Title of the current page
    """
    try:
        state = tool_context.state

        current_url = state.get("current_url", "about:blank")
        current_title = state.get("current_title", "(no page)")
        last_error = state.get("last_tool_error", "")

        # Gather recent tool events from the UI event queue
        ui_events = state.get("_ui_events", [])
        # Also look at completed events that were already drained
        recent_tools = []
        for evt in ui_events:
            if evt.get("type") == "tool_end":
                recent_tools.append({
                    "tool": evt.get("tool", "unknown"),
                    "status": evt.get("status", "unknown"),
                    "duration_ms": evt.get("duration_ms", 0),
                })

        # Build explanation
        parts = []
        parts.append(f"You're currently on: {current_title} ({current_url})")

        if recent_tools:
            parts.append("Recent actions:")
            for t in recent_tools[-5:]:  # Last 5 actions
                status_word = "succeeded" if t["status"] == "success" else "failed"
                parts.append(f"  - {t['tool']}: {status_word}")
        else:
            parts.append("No recent tool activity recorded in this turn.")

        if last_error:
            parts.append(f"Last error: {last_error}")
        else:
            parts.append("No errors in the last action.")

        return {
            "status": "success",
            "explanation": "\n".join(parts),
            "recent_tools": recent_tools[-5:],
            "last_error": last_error,
            "current_url": current_url,
            "current_title": current_title,
        }
    except Exception as e:
        return {
            "status": "success",
            "explanation": f"Could not retrieve full history: {e}",
            "recent_tools": [],
            "last_error": str(e),
            "current_url": "",
            "current_title": "",
        }


async def task_complete(
    summary: str,
    tool_context: ToolContext,
) -> dict:
    """Signal that the current user request has been fully handled.

    Call this tool ONLY when you have completed all steps for the user's
    request AND narrated the final result to them. This stops the task loop
    so Noor waits for the user's next instruction.

    Do NOT call this if there are still steps remaining (e.g., you navigated
    but haven't described the page yet, or you searched but haven't read
    the results).

    Args:
        summary: A brief summary of what was accomplished for logging
                 (e.g., "Navigated to Google and described the search page",
                 "Filled in the departure and arrival fields on the flight form").
        tool_context: ADK tool context.

    Returns:
        A dictionary confirming the task loop will stop.
    """
    try:
        tool_context.actions.escalate = True
        return {
            "status": "success",
            "message": f"Task complete: {summary}",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
