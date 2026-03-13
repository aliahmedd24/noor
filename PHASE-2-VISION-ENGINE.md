# PHASE 2: VISION ENGINE — GEMINI MULTIMODAL SCREEN ANALYSIS

## Objective

Build the vision processing pipeline that transforms raw screenshots into structured scene descriptions. This is the **core differentiator** of Noor and the **key judging criterion** for the UI Navigator category: "Does the agent demonstrate visual precision (understanding screen context) rather than blind clicking?"

Gemini's multimodal vision API receives the screenshot image and returns a structured understanding of the page — what elements are present, their types, positions, states, and relationships. This understanding drives all of Noor's subsequent actions.

---

## 2.1 — SCENE DESCRIPTION MODELS (`src/vision/models.py`)

Pydantic models that represent the structured output of Gemini's analysis of a screenshot.

```python
"""
Structured models for Gemini vision output.

These models represent the AI's understanding of what's on screen.
They are populated by prompting Gemini with a screenshot and requesting
structured JSON output matching these schemas.
"""
from pydantic import BaseModel, Field
from enum import Enum


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
    element_type: ElementType = Field(description="What kind of UI element this is")
    label: str = Field(description="The visible text or accessible label of the element")
    bounding_box: BoundingBox = Field(description="Pixel coordinates of the element")
    state: ElementState = Field(default=ElementState.NORMAL, description="Visual state")
    is_interactive: bool = Field(description="Whether this element can be clicked/interacted with")
    description: str = Field(default="", description="Brief description of what the element does or contains")
    value: str = Field(default="", description="Current value for input fields, selected option for dropdowns")


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
    page_type: str = Field(description="Category of page: search_results, article, form, login, shopping, homepage, dashboard, error_page, other")
    summary: str = Field(description="2-3 sentence human-readable summary of what is visible on the page, suitable for reading aloud to a blind user")
    visual_layout: str = Field(description="Brief description of the page's visual layout and structure")
    primary_action: str = Field(description="The most likely action a user would want to take on this page")
    interactive_elements: list[PageElement] = Field(description="All interactive elements visible on the page (buttons, links, inputs, etc.)")
    content_elements: list[PageElement] = Field(description="Key content elements (headings, paragraphs, images with descriptions)")
    regions: list[PageRegion] = Field(default_factory=list, description="Major page regions detected")
    has_cookie_banner: bool = Field(default=False, description="Whether a cookie consent banner is visible")
    has_modal: bool = Field(default=False, description="Whether a modal/dialog is currently displayed")
    scroll_position: str = Field(default="top", description="Approximate scroll position: top, middle, bottom")
    notable_colors: str = Field(default="", description="Any important color-based information (red error messages, green success indicators, etc.)")
```

---

## 2.2 — SCREEN ANALYZER (`src/vision/analyzer.py`)

The core vision engine that sends screenshots to Gemini and parses structured scene descriptions.

### Specification

```python
"""
ScreenAnalyzer — Gemini multimodal vision for web page understanding.

This module sends screenshots to Gemini's vision API and receives structured
scene descriptions. It is the AI 'eyes' of Noor.

Architecture:
- Uses google-genai SDK (via Vertex AI or AI Studio based on env config)
- Sends JPEG screenshots as image parts
- Prompts Gemini for structured JSON output matching SceneDescription schema
- Falls back to unstructured text description if JSON parsing fails
"""
from google import genai
from google.genai import types


class ScreenAnalyzer:
    """Analyzes screenshots using Gemini multimodal vision."""

    # Model for vision analysis (non-streaming, high-quality)
    VISION_MODEL = "gemini-2.5-flash"

    def __init__(self):
        """Initialize the GenAI client. Uses env vars for auth config."""
        self.client = genai.Client()

    async def analyze_screenshot(self, image_bytes: bytes,
                                  page_url: str = "",
                                  page_title: str = "",
                                  user_intent: str = "") -> SceneDescription:
        """
        Analyze a screenshot and return a structured scene description.

        Args:
            image_bytes: JPEG image bytes of the screenshot.
            page_url: Current page URL (provides context).
            page_title: Current page title (provides context).
            user_intent: What the user is trying to do (helps focus analysis).

        Returns:
            SceneDescription with all detected elements and layout info.
        """

    async def describe_for_narration(self, image_bytes: bytes,
                                      page_url: str = "",
                                      context: str = "") -> str:
        """
        Generate a natural-language narration of what's on screen.

        This is specifically for speaking aloud to the user — it should
        be conversational, concise, and prioritize actionable information.

        Args:
            image_bytes: JPEG screenshot bytes.
            page_url: Current URL for context.
            context: What the user was doing (e.g., "searching for flights").

        Returns:
            A string suitable for text-to-speech narration.
        """

    async def identify_click_target(self, image_bytes: bytes,
                                     target_description: str) -> tuple[int, int] | None:
        """
        Given a screenshot and a description of what to click, return coordinates.

        This is a focused analysis that identifies the pixel coordinates of a
        specific element described in natural language.

        Args:
            image_bytes: JPEG screenshot bytes.
            target_description: Natural language description of what to click
                               (e.g., "the blue Sign In button in the top right").

        Returns:
            (x, y) pixel coordinates of the center of the target element,
            or None if the element could not be found.
        """
```

### Vision Prompt Engineering

The quality of Noor's vision depends entirely on the prompts sent to Gemini. Here are the prompts to use:

#### Main Analysis Prompt (`src/agents/instructions/vision.txt`)

```text
You are Noor's vision system — the AI eyes for a visually impaired user navigating the web.

Analyze the provided screenshot of a web page and return a structured JSON description.

Context:
- Page URL: {page_url}
- Page Title: {page_title}
- User's current goal: {user_intent}

Your analysis MUST include:

1. **page_type**: Categorize the page (search_results, article, form, login, shopping, homepage, dashboard, error_page, other)

2. **summary**: Write 2-3 sentences describing what's on the page AS IF you are describing it to a blind person. Be specific and actionable. BAD: "This is a website." GOOD: "This is Google's search results page showing 10 results for 'cheap flights to Berlin'. The first result is from Skyscanner showing prices from 89 euros."

3. **visual_layout**: Describe the page structure briefly (e.g., "Header with logo and nav bar at top, main content area with a search form centered, footer with links at bottom")

4. **primary_action**: What would most users want to do here? (e.g., "Enter search terms in the search box", "Click the first search result", "Fill in the login form")

5. **interactive_elements**: List ALL clickable/interactive elements visible on screen. For each, provide:
   - element_type: button, link, text_input, dropdown, checkbox, etc.
   - label: The visible text or icon description
   - bounding_box: Approximate pixel coordinates {x, y, width, height} on the 1280x800 viewport
   - state: normal, focused, disabled, selected, etc.
   - is_interactive: true/false
   - description: What clicking/interacting with this element would do

6. **content_elements**: List key content elements (headings, important text, images)
   - For images: describe what the image shows
   - For headings: include the heading text
   - For important text: include key information

7. **has_cookie_banner**: Is there a cookie consent popup?
8. **has_modal**: Is there a modal/dialog overlay?
9. **notable_colors**: Any color-based indicators (red error text, green success, yellow warning)

COORDINATE SYSTEM: The viewport is 1280 pixels wide and 800 pixels tall. (0,0) is the top-left corner. Provide bounding boxes as {x, y, width, height} where x,y is the top-left corner of the element.

OUTPUT FORMAT: Return ONLY valid JSON matching the SceneDescription schema. No markdown, no commentary.
```

#### Narration Prompt

```text
You are Noor, a warm and helpful AI companion for a visually impaired person browsing the web.

Look at this screenshot and describe what you see in 2-4 natural, conversational sentences. You're speaking directly to the user.

Prioritize:
1. What kind of page this is
2. The most important content visible
3. What the user can do next (interactive elements)

Skip: navigation bars, footers, cookie banners, ads (unless the user is looking for them).

Be specific with numbers, names, and key details. Say things like "I can see 5 search results" not "there are some results."

Context about what the user is doing: {context}
```

#### Click Target Prompt

```text
Look at this screenshot (1280x800 pixels). The user wants to click: "{target_description}"

Identify the EXACT pixel coordinates of the CENTER of that element.

Return ONLY a JSON object: {"x": <number>, "y": <number>, "confidence": <0-1>, "element_found": true/false}

If the element is not visible on screen, return: {"element_found": false, "suggestion": "brief description of what you see instead"}
```

---

## 2.3 — VISION TOOLS FOR ADK (`src/tools/vision_tools.py`)

ADK tool wrappers that combine screenshot capture with vision analysis.

```python
async def analyze_current_page(user_intent: str = "") -> dict:
    """Capture a screenshot of the current page and analyze its contents.

    This tool takes a screenshot of the browser viewport and uses AI vision
    to understand what is displayed — including text, buttons, links, forms,
    images, and page layout. Use this tool whenever you need to understand
    what is currently on the screen.

    This is Noor's primary way of 'seeing' the web page.

    Args:
        user_intent: Optional description of what the user is trying to do.
                     This helps focus the analysis on relevant elements.
                     Example: "looking for the search box" or "trying to find flight prices"

    Returns:
        A dictionary containing:
        - status: 'success' or 'error'
        - page_type: Category of the page (search_results, article, form, etc.)
        - summary: Human-readable summary of the page
        - interactive_elements: List of clickable/interactive elements with coordinates
        - primary_action: The most likely next action
        - has_cookie_banner: Whether a cookie popup needs to be dismissed
        - has_modal: Whether a modal dialog is covering the content
    """


async def describe_page_aloud() -> dict:
    """Generate a natural spoken description of the current page for the user.

    Use this tool when the user asks 'what's on the screen?', 'what do you see?',
    'describe this page', 'where am I?', or similar questions about the current
    page content. The description is optimized for being read aloud.

    Returns:
        A dictionary containing:
        - status: 'success' or 'error'
        - narration: A conversational description suitable for text-to-speech
        - url: Current page URL
        - title: Current page title
    """


async def find_and_click(target_description: str) -> dict:
    """Find a specific element on the page by description and click it.

    This tool combines vision analysis with clicking. It takes a screenshot,
    uses AI to find the element matching the description, and clicks its
    center coordinates.

    Use this for commands like 'click the sign in button', 'open the first result',
    'click the search box'.

    Args:
        target_description: Natural language description of what to click.
                           Example: "the blue Sign In button", "the first search result",
                           "the search input field"

    Returns:
        A dictionary containing:
        - status: 'success' or 'error'
        - clicked: Whether an element was found and clicked
        - target: Description of what was clicked
        - coordinates: The (x, y) coordinates that were clicked
        - error: Error description if the element wasn't found
    """
```

---

## 2.4 — GEMINI API CALL PATTERNS

### Making Vision API Calls with google-genai

```python
from google import genai
from google.genai import types

client = genai.Client()

# Single image analysis
response = await client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Content(
            parts=[
                types.Part.from_image(
                    image=types.Image(
                        image_bytes=screenshot_bytes,
                        mime_type="image/jpeg"
                    )
                ),
                types.Part.from_text(analysis_prompt)
            ]
        )
    ],
    config=types.GenerateContentConfig(
        temperature=0.1,  # Low temperature for precise analysis
        max_output_tokens=4096,
        response_mime_type="application/json",  # Force JSON output
    )
)
```

### Key Implementation Details

1. **Use `response_mime_type="application/json"`** to force structured JSON output from Gemini — this dramatically improves parsing reliability
2. **Low temperature (0.1)** for consistent, precise element identification
3. **Image must be JPEG bytes** with mime_type `"image/jpeg"`
4. **Parse response with Pydantic**: `SceneDescription.model_validate_json(response.text)`
5. **Fallback handling**: If JSON parsing fails, re-prompt with a simpler instruction requesting just the summary
6. **Caching**: Cache the SceneDescription in ADK session state so the orchestrator can reference it without re-analyzing

---

## 2.5 — IMPLEMENTATION ORDER

1. **`src/vision/models.py`** — All Pydantic models
2. **`src/agents/instructions/vision.txt`** — Vision analysis prompt
3. **`src/vision/analyzer.py`** — ScreenAnalyzer class with all three methods
4. **`src/tools/vision_tools.py`** — ADK tool wrappers
5. **`tests/test_vision_analysis.py`** — Test with real screenshots

---

## 2.6 — ACCEPTANCE CRITERIA

- [ ] `ScreenAnalyzer.analyze_screenshot()` returns a valid `SceneDescription` from a Google.com screenshot
- [ ] Interactive elements have bounding boxes with reasonable coordinates (within 1280x800)
- [ ] `describe_for_narration()` returns natural-language text suitable for speech
- [ ] `identify_click_target()` correctly identifies the Google search box coordinates
- [ ] JSON output parsing succeeds with `response_mime_type="application/json"`
- [ ] Fallback to text description works when JSON parsing fails
- [ ] All ADK tool functions have comprehensive docstrings
- [ ] End-to-end: screenshot → analyze → find search box → click → type → works

---

## 2.7 — PERFORMANCE TARGETS

| Operation | Target Latency | Notes |
|-----------|---------------|-------|
| Screenshot capture | <200ms | Playwright viewport screenshot |
| Vision analysis (full) | <3s | Gemini 2.5 Flash with JSON output |
| Narration generation | <2s | Simpler prompt, text output |
| Click target identification | <1.5s | Focused single-element prompt |
| Grid overlay rendering | <100ms | Pillow image manipulation |

Total loop (screenshot → analyze → act): Target **<5 seconds**. This is acceptable because Noor narrates "Let me take a look at the page..." during processing, keeping the user informed.
