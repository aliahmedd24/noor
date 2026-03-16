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
