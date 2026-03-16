"""ADK Plugins — cross-cutting concerns applied globally to all agents.

Plugins run BEFORE agent-level callbacks and apply to every agent, tool,
and LLM call in the runner.  We use ADK's native prebuilt plugins rather
than writing custom lifecycle hooks.

Available prebuilt plugins in google.adk.plugins:
- ReflectAndRetryToolPlugin: Auto-retry failed tools with LLM reflection
- LoggingPlugin: Log every lifecycle event (agent/tool/model)
- DebugLoggingPlugin: Verbose debug-level logging for development
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
      Critical for Noor because browser actions are inherently flaky
      (elements may shift, pages may still be loading). Max 2 retries.
    - **LoggingPlugin** (production) / **DebugLoggingPlugin** (dev):
      Logs every agent/tool/model lifecycle event for Cloud Logging
      observability. DebugLoggingPlugin is used when NOOR_LOG_LEVEL=DEBUG.

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
