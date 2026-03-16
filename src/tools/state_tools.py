"""Session state retrieval tools for Noor ADK agents.

Provides the get_state_detail tool that allows agents to retrieve full,
untruncated state values when the minified summaries in their instructions
are insufficient.
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
                "error": f"Unknown state key '{key}'. Allowed keys: {', '.join(sorted(_ALLOWED_KEYS))}",
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
