"""
Noor Agent — Root ADK agent definition.

This module assembles the multi-agent hierarchy and exports the root_agent
that ADK uses as the entry point for all interactions.

Architecture:
    NoorOrchestrator (root)
    ├── ScreenVisionAgent
    ├── NavigatorAgent
    └── PageSummarizerAgent
"""

from src.agents.orchestrator import orchestrator_agent
from src.agents.vision_agent import vision_agent
from src.agents.navigator_agent import navigator_agent
from src.agents.summarizer_agent import summarizer_agent

from src.tools.vision_tools import (
    analyze_current_page,
    describe_page_aloud,
    find_and_click,
)
from src.tools.browser_tools import (
    navigate_to_url,
    click_at_coordinates,
    click_element_by_text,
    type_into_field,
    scroll_down,
    scroll_up,
    press_enter,
    press_tab,
    go_back_in_browser,
    take_screenshot_of_page,
    get_current_page_url,
)
from src.tools.page_tools import extract_page_text, get_page_metadata

# Wire tools into sub-agents
vision_agent.tools = [
    analyze_current_page,
    describe_page_aloud,
    find_and_click,
]

navigator_agent.tools = [
    navigate_to_url,
    click_at_coordinates,
    click_element_by_text,
    type_into_field,
    scroll_down,
    scroll_up,
    press_enter,
    press_tab,
    go_back_in_browser,
    take_screenshot_of_page,
    get_current_page_url,
]

summarizer_agent.tools = [
    analyze_current_page,
    describe_page_aloud,
    extract_page_text,
    get_page_metadata,
    scroll_down,
]

# Wire sub-agents into the orchestrator
orchestrator_agent.sub_agents = [
    vision_agent,
    navigator_agent,
    summarizer_agent,
]

# ADK convention: the framework discovers agents via this name
root_agent = orchestrator_agent
