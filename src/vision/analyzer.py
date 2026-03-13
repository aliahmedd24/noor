"""ScreenAnalyzer — Gemini multimodal vision for web page understanding.

This module sends screenshots to Gemini's vision API and receives structured
scene descriptions. It is the AI 'eyes' of Noor.

Architecture:
- Uses google-genai SDK (via Vertex AI or AI Studio based on env config)
- Sends JPEG screenshots as image parts
- Prompts Gemini for structured JSON output matching SceneDescription schema
- Falls back to unstructured text description if JSON parsing fails
"""

from __future__ import annotations

import json

import structlog
from google import genai
from google.genai import types

from src.vision.models import SceneDescription

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_ANALYSIS_PROMPT = """\
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
   - bounding_box: Approximate pixel coordinates {{x, y, width, height}} on the 1280x800 viewport
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

COORDINATE SYSTEM: The viewport is 1280 pixels wide and 800 pixels tall. (0,0) is the top-left corner. Provide bounding boxes as {{x, y, width, height}} where x,y is the top-left corner of the element.

OUTPUT FORMAT: Return ONLY valid JSON matching the SceneDescription schema. No markdown, no commentary.\
"""

_NARRATION_PROMPT = """\
You are Noor, a warm and helpful AI companion for a visually impaired person browsing the web.

Look at this screenshot and describe what you see in 2-4 natural, conversational sentences. You're speaking directly to the user.

Prioritize:
1. What kind of page this is
2. The most important content visible
3. What the user can do next (interactive elements)

Skip: navigation bars, footers, cookie banners, ads (unless the user is looking for them).

Be specific with numbers, names, and key details. Say things like "I can see 5 search results" not "there are some results."

Context about what the user is doing: {context}\
"""

_CLICK_TARGET_PROMPT = """\
Look at this screenshot (1280x800 pixels). The user wants to click: "{target_description}"

Identify the EXACT pixel coordinates of the CENTER of that element.

Return ONLY a JSON object: {{"x": <number>, "y": <number>, "confidence": <0-1>, "element_found": true/false}}

If the element is not visible on screen, return: {{"element_found": false, "suggestion": "brief description of what you see instead"}}\
"""


class ScreenAnalyzer:
    """Analyzes screenshots using Gemini multimodal vision."""

    VISION_MODEL = "gemini-2.5-flash"

    def __init__(self) -> None:
        """Initialize the GenAI client.

        Uses Vertex AI with Application Default Credentials.
        Reads project/location from src.config.Settings (which loads .env).
        """
        from src.config import settings

        use_vertex = settings.google_genai_use_vertexai.upper() == "TRUE"
        if use_vertex:
            self.client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
            )
        else:
            self.client = genai.Client(
                api_key=settings.google_api_key,
            )

    async def analyze_screenshot(
        self,
        image_bytes: bytes,
        page_url: str = "",
        page_title: str = "",
        user_intent: str = "",
    ) -> SceneDescription:
        """Analyze a screenshot and return a structured scene description.

        Args:
            image_bytes: JPEG image bytes of the screenshot.
            page_url: Current page URL (provides context).
            page_title: Current page title (provides context).
            user_intent: What the user is trying to do (helps focus analysis).

        Returns:
            SceneDescription with all detected elements and layout info.
        """
        prompt = _ANALYSIS_PROMPT.format(
            page_url=page_url or "unknown",
            page_title=page_title or "unknown",
            user_intent=user_intent or "general browsing",
        )

        response = await self.client.aio.models.generate_content(
            model=self.VISION_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/jpeg",
                        ),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
                response_mime_type="application/json",
            ),
        )

        try:
            data = json.loads(response.text)
            # Inject context fields Gemini doesn't return
            data.setdefault("page_url", page_url or "")
            data.setdefault("page_title", page_title or "")
            scene = SceneDescription.model_validate(data)
            logger.info(
                "vision_analysis_complete",
                page_type=scene.page_type,
                interactive_count=len(scene.interactive_elements),
                content_count=len(scene.content_elements),
            )
            return scene
        except Exception as parse_err:
            logger.warning(
                "json_parse_failed_falling_back",
                error=str(parse_err),
            )
            return await self._fallback_analysis(
                image_bytes, page_url, page_title, response.text
            )

    async def describe_for_narration(
        self,
        image_bytes: bytes,
        page_url: str = "",
        context: str = "",
    ) -> str:
        """Generate a natural-language narration of what's on screen.

        This is specifically for speaking aloud to the user — it should
        be conversational, concise, and prioritize actionable information.

        Args:
            image_bytes: JPEG screenshot bytes.
            page_url: Current URL for context.
            context: What the user was doing (e.g., "searching for flights").

        Returns:
            A string suitable for text-to-speech narration.
        """
        prompt = _NARRATION_PROMPT.format(
            context=context or "general browsing",
        )

        response = await self.client.aio.models.generate_content(
            model=self.VISION_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/jpeg",
                        ),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=512,
            ),
        )

        narration = response.text.strip()
        logger.info("narration_generated", length=len(narration))
        return narration

    async def identify_click_target(
        self,
        image_bytes: bytes,
        target_description: str,
    ) -> tuple[int, int] | None:
        """Given a screenshot and a description of what to click, return coordinates.

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
        prompt = _CLICK_TARGET_PROMPT.format(
            target_description=target_description,
        )

        response = await self.client.aio.models.generate_content(
            model=self.VISION_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type="image/jpeg",
                        ),
                        types.Part.from_text(text=prompt),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=256,
                response_mime_type="application/json",
            ),
        )

        try:
            raw = response.text or ""
            if not raw.strip():
                logger.warning(
                    "click_target_empty_response",
                    target=target_description,
                )
                return None
            result = json.loads(raw)
            if result.get("element_found", False):
                x = int(result["x"])
                y = int(result["y"])
                confidence = float(result.get("confidence", 0))
                logger.info(
                    "click_target_found",
                    target=target_description,
                    x=x,
                    y=y,
                    confidence=confidence,
                )
                return (x, y)
            logger.info(
                "click_target_not_found",
                target=target_description,
                suggestion=result.get("suggestion", ""),
            )
            return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(
                "click_target_parse_failed",
                target=target_description,
                error=str(e),
            )
            return None

    async def _fallback_analysis(
        self,
        image_bytes: bytes,
        page_url: str,
        page_title: str,
        raw_text: str,
    ) -> SceneDescription:
        """Create a minimal SceneDescription when JSON parsing fails.

        Uses the raw text from Gemini as the summary, providing at least
        a text description even when structured parsing fails.

        Args:
            image_bytes: Original screenshot bytes.
            page_url: Page URL.
            page_title: Page title.
            raw_text: Raw response text from Gemini.

        Returns:
            A minimal SceneDescription with the raw text as summary.
        """
        logger.info("using_fallback_analysis", url=page_url)
        return SceneDescription(
            page_url=page_url,
            page_title=page_title,
            page_type="other",
            summary=raw_text[:500] if raw_text else "Unable to analyze page.",
            visual_layout="Unable to determine layout structure.",
            primary_action="Unable to determine primary action.",
            interactive_elements=[],
            content_elements=[],
        )
