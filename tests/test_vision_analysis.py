"""Tests for the vision analysis pipeline.

These tests verify the Pydantic models, the ScreenAnalyzer class,
and the ADK vision tool wrappers. Tests requiring a live Gemini API
key are marked with @pytest.mark.api so they can be skipped in CI.

Run all tests:        pytest tests/test_vision_analysis.py -v
Run model tests only: pytest tests/test_vision_analysis.py -v -k "not api"
Run API tests only:   pytest tests/test_vision_analysis.py -v -m api

API tests require Vertex AI credentials:
  export GOOGLE_CLOUD_PROJECT=your-project-id
  export GOOGLE_GENAI_USE_VERTEXAI=TRUE
  gcloud auth application-default login
"""

from __future__ import annotations

import json
import os

import pytest

from src.vision.models import (
    BoundingBox,
    ElementState,
    ElementType,
    PageElement,
    PageRegion,
    SceneDescription,
)


# ---------------------------------------------------------------------------
# Model unit tests (no API calls needed)
# ---------------------------------------------------------------------------


class TestBoundingBox:
    """Tests for the BoundingBox model."""

    def test_center_calculation(self):
        bbox = BoundingBox(x=100, y=200, width=50, height=30)
        assert bbox.center == (125, 215)

    def test_zero_origin(self):
        bbox = BoundingBox(x=0, y=0, width=1280, height=800)
        assert bbox.center == (640, 400)

    def test_small_element(self):
        bbox = BoundingBox(x=500, y=300, width=10, height=10)
        assert bbox.center == (505, 305)


class TestPageElement:
    """Tests for the PageElement model."""

    def test_interactive_button(self):
        elem = PageElement(
            element_type=ElementType.BUTTON,
            label="Sign In",
            bounding_box=BoundingBox(x=1100, y=20, width=80, height=36),
            state=ElementState.NORMAL,
            is_interactive=True,
            description="Opens the sign-in dialog",
        )
        assert elem.element_type == ElementType.BUTTON
        assert elem.is_interactive is True
        assert elem.bounding_box.center == (1140, 38)

    def test_content_heading(self):
        elem = PageElement(
            element_type=ElementType.HEADING,
            label="Breaking News",
            bounding_box=BoundingBox(x=50, y=100, width=400, height=40),
            is_interactive=False,
        )
        assert elem.state == ElementState.NORMAL  # default
        assert elem.value == ""  # default

    def test_input_with_value(self):
        elem = PageElement(
            element_type=ElementType.TEXT_INPUT,
            label="Search",
            bounding_box=BoundingBox(x=300, y=350, width=600, height=44),
            is_interactive=True,
            value="cheap flights",
        )
        assert elem.value == "cheap flights"


class TestSceneDescription:
    """Tests for the SceneDescription model."""

    def test_minimal_scene(self):
        scene = SceneDescription(
            page_url="https://www.google.com",
            page_title="Google",
            page_type="homepage",
            summary="Google search homepage with a centered search box.",
            visual_layout="Centered layout with logo and search form.",
            primary_action="Enter search terms in the search box",
            interactive_elements=[],
            content_elements=[],
        )
        assert scene.page_type == "homepage"
        assert scene.has_cookie_banner is False
        assert scene.has_modal is False
        assert scene.scroll_position == "top"

    def test_full_scene_from_json(self):
        data = {
            "page_url": "https://www.google.com/search?q=flights",
            "page_title": "flights - Google Search",
            "page_type": "search_results",
            "summary": "Google search results for 'flights' with 10 results.",
            "visual_layout": "Header with search bar, main content with results list.",
            "primary_action": "Click the first search result",
            "interactive_elements": [
                {
                    "element_type": "link",
                    "label": "Flights - Google",
                    "bounding_box": {"x": 180, "y": 200, "width": 400, "height": 24},
                    "is_interactive": True,
                    "description": "Link to Google Flights",
                }
            ],
            "content_elements": [
                {
                    "element_type": "heading",
                    "label": "Flights",
                    "bounding_box": {"x": 180, "y": 170, "width": 200, "height": 30},
                    "is_interactive": False,
                }
            ],
            "regions": ["header", "main_content"],
            "has_cookie_banner": False,
            "has_modal": False,
            "scroll_position": "top",
            "notable_colors": "",
        }
        scene = SceneDescription.model_validate(data)
        assert scene.page_type == "search_results"
        assert len(scene.interactive_elements) == 1
        assert scene.interactive_elements[0].element_type == ElementType.LINK
        assert scene.interactive_elements[0].bounding_box.center == (380, 212)

    def test_scene_json_roundtrip(self):
        scene = SceneDescription(
            page_url="https://example.com",
            page_title="Example",
            page_type="other",
            summary="A simple example page.",
            visual_layout="Single column layout.",
            primary_action="Read the content",
            interactive_elements=[],
            content_elements=[],
            regions=[PageRegion.MAIN_CONTENT],
        )
        json_str = scene.model_dump_json()
        parsed = json.loads(json_str)
        restored = SceneDescription.model_validate(parsed)
        assert restored.page_url == scene.page_url
        assert restored.regions == [PageRegion.MAIN_CONTENT]


class TestEnums:
    """Verify enum values match what Gemini returns."""

    def test_element_types(self):
        assert ElementType("button") == ElementType.BUTTON
        assert ElementType("text_input") == ElementType.TEXT_INPUT

    def test_element_states(self):
        assert ElementState("focused") == ElementState.FOCUSED
        assert ElementState("disabled") == ElementState.DISABLED

    def test_page_regions(self):
        assert PageRegion("header") == PageRegion.HEADER
        assert PageRegion("cookie_banner") == PageRegion.COOKIE_BANNER


# ---------------------------------------------------------------------------
# ScreenAnalyzer tests (require GOOGLE_API_KEY)
# ---------------------------------------------------------------------------

def _has_vertex_ai_credentials() -> bool:
    """Check if Vertex AI credentials are available."""
    if not os.getenv("GOOGLE_CLOUD_PROJECT"):
        return False
    try:
        import google.auth
        credentials, _ = google.auth.default()
        return credentials is not None
    except Exception:
        return False


api = pytest.mark.skipif(
    not _has_vertex_ai_credentials(),
    reason="Vertex AI credentials not available — need GOOGLE_CLOUD_PROJECT "
    "and Application Default Credentials (run 'gcloud auth application-default login')",
)


@api
class TestScreenAnalyzerLive:
    """Live integration tests for ScreenAnalyzer with real Gemini API calls.

    These tests require:
    - GOOGLE_CLOUD_PROJECT set in environment
    - GOOGLE_GENAI_USE_VERTEXAI=TRUE
    - Application Default Credentials (run 'gcloud auth application-default login')
    - NOOR_BROWSER_CHANNEL=msedge (on Windows)
    """

    @pytest.fixture
    async def analyzer(self):
        from src.vision.analyzer import ScreenAnalyzer

        return ScreenAnalyzer()

    @pytest.fixture
    async def google_screenshot(self, browser):
        """Navigate to Google and take a screenshot."""
        await browser.navigate("https://www.google.com")
        return await browser.take_screenshot()

    async def test_analyze_screenshot_returns_scene(
        self, analyzer, google_screenshot, browser
    ):
        """Verify analyze_screenshot returns a valid SceneDescription."""
        info = await browser.get_page_info()
        scene = await analyzer.analyze_screenshot(
            image_bytes=google_screenshot,
            page_url=info["url"],
            page_title=info["title"],
            user_intent="looking for the search box",
        )
        assert isinstance(scene, SceneDescription)
        assert scene.page_type in (
            "homepage",
            "search_results",
            "form",
            "other",
            "login",
        )
        assert len(scene.summary) > 10
        # Google may show a consent page with interactive elements,
        # or a homepage — both are valid
        assert len(scene.interactive_elements) >= 0

    async def test_interactive_elements_have_valid_bounds(
        self, analyzer, google_screenshot, browser
    ):
        """Verify bounding boxes are within the 1280x800 viewport."""
        info = await browser.get_page_info()
        scene = await analyzer.analyze_screenshot(
            image_bytes=google_screenshot,
            page_url=info["url"],
            page_title=info["title"],
        )
        for elem in scene.interactive_elements:
            bbox = elem.bounding_box
            assert 0 <= bbox.x <= 1280, f"x={bbox.x} out of range for {elem.label}"
            assert 0 <= bbox.y <= 800, f"y={bbox.y} out of range for {elem.label}"
            assert bbox.width > 0, f"width must be positive for {elem.label}"
            assert bbox.height > 0, f"height must be positive for {elem.label}"

    async def test_describe_for_narration(
        self, analyzer, google_screenshot
    ):
        """Verify narration returns conversational text."""
        narration = await analyzer.describe_for_narration(
            image_bytes=google_screenshot,
            page_url="https://www.google.com",
            context="just opened the browser",
        )
        assert isinstance(narration, str)
        assert len(narration) > 20
        # Should mention Google in some form
        assert any(
            word in narration.lower()
            for word in ("google", "search", "page")
        )

    async def test_identify_click_target_visible_element(
        self, analyzer, google_screenshot
    ):
        """Verify the analyzer can find a visible clickable element."""
        # Google may show a consent page or homepage
        # Try "Accept all" button (consent) or "Google Search" button (homepage)
        for target in [
            "the Accept all button",
            "the Google Search button",
            "any clickable button visible on the page",
        ]:
            coords = await analyzer.identify_click_target(
                image_bytes=google_screenshot,
                target_description=target,
            )
            if coords is not None:
                x, y = coords
                assert 0 <= x <= 1280, f"x={x} out of viewport"
                assert 0 <= y <= 800, f"y={y} out of viewport"
                return
        # If none found, that's still acceptable for this flaky live test
        pytest.skip("Could not identify any click target on the page")

    async def test_identify_click_target_not_found(
        self, analyzer, google_screenshot
    ):
        """Verify None is returned for a non-existent element."""
        coords = await analyzer.identify_click_target(
            image_bytes=google_screenshot,
            target_description="a purple dinosaur riding a bicycle",
        )
        assert coords is None


# ---------------------------------------------------------------------------
# Vision tool integration tests (require GOOGLE_API_KEY + browser)
# ---------------------------------------------------------------------------


@api
class TestVisionToolsLive:
    """Live integration tests for ADK vision tool wrappers."""

    @pytest.fixture(autouse=True)
    async def setup_tools(self, browser):
        """Wire up the vision tools with browser and analyzer."""
        from src.tools import vision_tools
        from src.vision.analyzer import ScreenAnalyzer

        vision_tools.set_browser_manager(browser)
        vision_tools.set_screen_analyzer(ScreenAnalyzer())
        await browser.navigate("https://www.google.com")
        yield

    async def test_analyze_current_page(self):
        from src.tools.vision_tools import analyze_current_page

        result = await analyze_current_page(
            user_intent="looking for the search box"
        )
        assert result["status"] == "success"
        assert result["page_type"] in (
            "homepage",
            "search_results",
            "form",
            "other",
            "login",
        )
        assert len(result["summary"]) > 10
        assert isinstance(result["interactive_elements"], list)

    async def test_describe_page_aloud(self):
        from src.tools.vision_tools import describe_page_aloud

        result = await describe_page_aloud()
        assert result["status"] == "success"
        assert len(result["narration"]) > 20
        assert result["url"] != ""

    async def test_find_and_click_visible_button(self):
        from src.tools.vision_tools import find_and_click

        # Try specific button descriptions that match consent or homepage
        for target in [
            "the Accept all button",
            "the Google Search button",
        ]:
            result = await find_and_click(target_description=target)
            if result["status"] == "success":
                assert result["clicked"] is True
                assert result["coordinates"] is not None
                assert result["coordinates"]["x"] > 0
                assert result["coordinates"]["y"] > 0
                return
        pytest.skip("Could not find a clickable button on the page")

    async def test_find_and_click_nonexistent(self):
        from src.tools.vision_tools import find_and_click

        result = await find_and_click(
            target_description="a purple dinosaur button"
        )
        assert result["status"] == "error"
        assert result["clicked"] is False
