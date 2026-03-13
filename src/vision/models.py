"""Structured models for Gemini vision output.

These models represent the AI's understanding of what's on screen.
They are populated by prompting Gemini with a screenshot and requesting
structured JSON output matching these schemas.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ElementType(str, Enum):
    """Types of interactive and content elements on a page."""

    BUTTON = "button"
    LINK = "link"
    TEXT_INPUT = "text_input"
    TEXTAREA = "textarea"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    IMAGE = "image"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    NAVIGATION = "navigation"
    FORM = "form"
    TABLE = "table"
    LIST = "list"
    DIALOG = "dialog"
    MENU = "menu"
    TAB = "tab"
    ICON = "icon"
    VIDEO = "video"
    OTHER = "other"


class ElementState(str, Enum):
    """Visual state of an element."""

    NORMAL = "normal"
    FOCUSED = "focused"
    DISABLED = "disabled"
    SELECTED = "selected"
    CHECKED = "checked"
    UNCHECKED = "unchecked"
    EXPANDED = "expanded"
    COLLAPSED = "collapsed"
    LOADING = "loading"
    ERROR = "error"


class BoundingBox(BaseModel):
    """Pixel coordinates of an element's bounding box."""

    x: int = Field(description="Left edge x-coordinate")
    y: int = Field(description="Top edge y-coordinate")
    width: int = Field(description="Width in pixels")
    height: int = Field(description="Height in pixels")

    @property
    def center(self) -> tuple[int, int]:
        """Return the center point of the bounding box."""
        return (self.x + self.width // 2, self.y + self.height // 2)


class PageElement(BaseModel):
    """A single element identified on the page."""

    element_type: ElementType = Field(
        description="What kind of UI element this is"
    )
    label: str = Field(
        description="The visible text or accessible label of the element"
    )
    bounding_box: BoundingBox = Field(
        description="Pixel coordinates of the element"
    )
    state: ElementState = Field(
        default=ElementState.NORMAL, description="Visual state"
    )
    is_interactive: bool = Field(
        description="Whether this element can be clicked/interacted with"
    )
    description: str = Field(
        default="",
        description="Brief description of what the element does or contains",
    )
    value: str = Field(
        default="",
        description="Current value for input fields, selected option for dropdowns",
    )


class PageRegion(str, Enum):
    """Major regions of a web page."""

    HEADER = "header"
    NAVIGATION = "navigation"
    MAIN_CONTENT = "main_content"
    SIDEBAR = "sidebar"
    FOOTER = "footer"
    MODAL = "modal"
    COOKIE_BANNER = "cookie_banner"
    ADVERTISEMENT = "advertisement"


class SceneDescription(BaseModel):
    """Complete structured description of a web page screenshot.

    This is the primary output of the Vision Engine and the primary input
    to the Navigator Agent for action planning.
    """

    page_url: str = Field(description="URL of the page")
    page_title: str = Field(description="Title of the page")
    page_type: str = Field(
        description="Category of page: search_results, article, form, login, "
        "shopping, homepage, dashboard, error_page, other"
    )
    summary: str = Field(
        description="2-3 sentence human-readable summary of what is visible "
        "on the page, suitable for reading aloud to a blind user"
    )
    visual_layout: str = Field(
        description="Brief description of the page's visual layout and structure"
    )
    primary_action: str = Field(
        description="The most likely action a user would want to take on this page"
    )
    interactive_elements: list[PageElement] = Field(
        description="All interactive elements visible on the page "
        "(buttons, links, inputs, etc.)"
    )
    content_elements: list[PageElement] = Field(
        description="Key content elements (headings, paragraphs, images with descriptions)"
    )
    regions: list[PageRegion] = Field(
        default_factory=list, description="Major page regions detected"
    )
    has_cookie_banner: bool = Field(
        default=False, description="Whether a cookie consent banner is visible"
    )
    has_modal: bool = Field(
        default=False, description="Whether a modal/dialog is currently displayed"
    )
    scroll_position: str = Field(
        default="top",
        description="Approximate scroll position: top, middle, bottom",
    )
    notable_colors: str = Field(
        default="",
        description="Any important color-based information "
        "(red error messages, green success indicators, etc.)",
    )
