"""ADK Plugins — cross-cutting concerns applied globally to all agents.

Plugins run BEFORE agent-level callbacks and apply to every agent, tool,
and LLM call in the runner.
"""

from __future__ import annotations

import os

from google.adk.plugins import (
    ReflectAndRetryToolPlugin,
    LoggingPlugin,
    DebugLoggingPlugin,
)


def get_plugins() -> list:
    """Return the list of ADK plugins to register on the Runner or App.

    Plugins included:
    - **ReflectAndRetryToolPlugin**: Automatically detects tool failures
      and prompts the model to try a different approach (self-healing).
      Max 2 retries.
    - **LoggingPlugin** (production) / **DebugLoggingPlugin** (dev):
      Logs every agent/tool/model lifecycle event.

    Returns:
        A list of plugin instances ready for ``Runner(plugins=...)``
        or ``App(plugins=...)``.
    """
    plugins = [
        ReflectAndRetryToolPlugin(max_retries=2),
    ]

    log_level = os.getenv("NOOR_LOG_LEVEL", "INFO").upper()
    if log_level == "DEBUG":
        plugins.append(DebugLoggingPlugin())
    else:
        plugins.append(LoggingPlugin())

    return plugins
