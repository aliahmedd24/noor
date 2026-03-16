"""Pydantic output schemas for ADK agent structured output.

These models define the contract between sub-agents and the orchestrator.
Each sub-agent uses ``output_schema`` so its output is validated and stored
as structured JSON in session state via ``output_key``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VisionOutput(BaseModel):
    """Structured output from ScreenVisionAgent."""

    page_type: str = Field(
        description="Category: search_results, article, form, login, shopping, homepage, other"
    )
    summary: str = Field(
        description="2-3 sentence description of the page suitable for reading aloud"
    )
    interactive_elements: list[str] = Field(
        description="List of interactive elements with labels and approximate positions"
    )
    primary_action: str = Field(
        description="The most likely next action the user would want to take"
    )
    has_cookie_banner: bool = Field(
        default=False, description="Whether a cookie consent banner is blocking content"
    )
    has_modal: bool = Field(
        default=False, description="Whether a modal dialog is covering the page"
    )


class NavigationOutput(BaseModel):
    """Structured output from NavigatorAgent."""

    action_taken: str = Field(
        description="What browser action was performed (e.g. 'clicked Search button', 'typed query')"
    )
    success: bool = Field(description="Whether the action completed successfully")
    current_url: str = Field(default="", description="URL after the action")
    current_title: str = Field(default="", description="Page title after the action")
    error: str = Field(default="", description="Error description if action failed")
    needs_followup: bool = Field(
        default=False,
        description="Whether another action is needed (e.g. page still loading, element not found)",
    )


class SummaryOutput(BaseModel):
    """Structured output from PageSummarizerAgent."""

    page_type: str = Field(
        description="Type of content: article, search_results, product, form, menu, other"
    )
    title: str = Field(description="Page or article title")
    summary: str = Field(
        description="Concise spoken summary of the page content, prioritizing most important info"
    )
    key_items: list[str] = Field(
        default_factory=list,
        description="Numbered list of key items (search results, products, headlines, form fields)",
    )
    has_more_content: bool = Field(
        default=False, description="Whether scrolling would reveal more content"
    )
