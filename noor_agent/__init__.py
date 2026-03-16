"""ADK agent definitions — exports root_agent and app for the ADK framework."""

from . import agent

root_agent = agent.root_agent
streaming_root_agent = agent.streaming_root_agent
app = agent.app

__all__ = ["root_agent", "streaming_root_agent", "app"]
