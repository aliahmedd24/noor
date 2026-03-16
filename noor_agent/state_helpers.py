"""State helpers for dynamic instruction injection.

Provides utilities to minify session state values so that agent instruction
prompts stay concise. Large state values (e.g., full vision analysis JSON)
are truncated with a pointer to the ``get_state_detail`` tool.
"""

from __future__ import annotations

_TRUNCATABLE_KEYS = frozenset({
    "vision_analysis",
    "navigation_result",
    "page_summary",
})

_ALL_STATE_KEYS = [
    "vision_analysis",
    "navigation_result",
    "page_summary",
    "current_url",
    "current_title",
    "last_tool_error",
]


def minify_state(state: dict, max_chars: int = 200) -> dict:
    """Return a copy of relevant state keys with large values truncated.

    Args:
        state: The full session state dictionary.
        max_chars: Maximum character length before truncation.

    Returns:
        A dict with the same keys but values truncated where appropriate.
    """
    result = {}
    for key in _ALL_STATE_KEYS:
        val = str(state.get(key, ""))
        if len(val) > max_chars and key in _TRUNCATABLE_KEYS:
            result[key] = val[:max_chars] + "... [use get_state_detail tool for full data]"
        else:
            result[key] = val
    return result
