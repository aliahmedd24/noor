# PHASE 6: INTEGRATION, DEMO & HACKATHON SUBMISSION

## Objective

Bring all components together, polish the end-to-end experience, create the demo scenarios, record the submission video, and prepare all hackathon deliverables. This phase addresses the **Demo & Presentation (30%)** judging criterion and all bonus point opportunities.

---

## 6.1 — END-TO-END INTEGRATION CHECKLIST

Before creating the demo, verify every link in the chain works:

```
User speaks → mic capture → WebSocket → ADK LiveRequestQueue
→ Gemini Live API (speech-to-intent) → NoorOrchestrator
→ delegates to ScreenVisionAgent/NavigatorAgent/PageSummarizerAgent
→ sub-agent calls tools (screenshot, Gemini vision, Playwright action)
→ result flows back through session state → Orchestrator narrates
→ Gemini Live API (text-to-speech) → WebSocket → speaker playback
```

### Integration Test Script (`tests/test_integration.py`)

```python
"""
End-to-end integration tests for Noor.

These tests simulate real user scenarios by running the full agent pipeline
with a real browser and Gemini API calls.
"""
import pytest
from src.agents import root_agent
from src.browser.manager import BrowserManager
from src.tools.browser_tools import set_browser_manager
from src.tools.vision_tools import set_browser_manager as set_vision_browser
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


@pytest.fixture
async def noor_system():
    """Set up the full Noor system for testing."""
    # Start browser
    browser = BrowserManager(headless=True)
    await browser.start()
    set_browser_manager(browser)
    set_vision_browser(browser)

    # Set up ADK runner
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="noor-test",
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name="noor-test",
        user_id="test-user",
    )

    yield runner, session

    await browser.stop()


async def send_message(runner, session, text: str) -> str:
    """Send a text message to Noor and collect the response."""
    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text)]
    )
    responses = []
    async for event in runner.run_async(
        session_id=session.id,
        user_id="test-user",
        new_message=content,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    responses.append(part.text)
    return " ".join(responses)


async def test_navigate_to_google(noor_system):
    runner, session = noor_system
    response = await send_message(runner, session, "Go to google.com")
    assert any(word in response.lower() for word in ["google", "search", "navigated"])


async def test_describe_page(noor_system):
    runner, session = noor_system
    await send_message(runner, session, "Go to google.com")
    response = await send_message(runner, session, "What do you see on the screen?")
    assert any(word in response.lower() for word in ["search", "google", "page"])


async def test_search_flow(noor_system):
    runner, session = noor_system
    response = await send_message(runner, session, "Search Google for weather in Bremen")
    assert any(word in response.lower() for word in ["weather", "bremen", "results", "search"])


async def test_read_results(noor_system):
    runner, session = noor_system
    await send_message(runner, session, "Go to BBC News")
    response = await send_message(runner, session, "Read me the top headlines")
    # Should contain actual news content
    assert len(response) > 50


async def test_go_back(noor_system):
    runner, session = noor_system
    await send_message(runner, session, "Go to google.com")
    await send_message(runner, session, "Go to bbc.com")
    response = await send_message(runner, session, "Go back to the previous page")
    assert any(word in response.lower() for word in ["google", "back", "previous"])
```

---

## 6.2 — DEMO SCENARIOS

These are the 3 scenarios to showcase in the 4-minute demo video. Each is designed to hit specific judging criteria.

### Scenario 1: "Help me search for flights" (≈90 seconds)

**Demonstrates:** Full navigation loop, form interaction, result reading, multi-step agentic flow.

```
USER: "Hey Noor, I need to find cheap flights from Cairo to Berlin for next Friday."

NOOR: "Sure! Let me search for flights from Cairo to Berlin. I'll open Google
       Flights for you."
       [NavigatorAgent: navigate to google.com/travel/flights]

NOOR: "I've opened Google Flights. I can see a search form with fields for
       departure city, destination, and dates. Let me fill those in for you."
       [ScreenVisionAgent: analyze page]
       [NavigatorAgent: click departure field, type "Cairo"]
       [NavigatorAgent: click destination field, type "Berlin"]
       [NavigatorAgent: click date field, select next Friday]
       [NavigatorAgent: click Search button]

NOOR: "The search results are loading... I can see 8 flight options.
       The cheapest is with EgyptAir at 289 euros, departing at 6:15 AM
       with one stop in Istanbul. The second option is Lufthansa at 340
       euros, a direct flight departing at 10:30 AM. Would you like to
       hear more options, or shall I click on one of these?"

USER: "Tell me about the direct Lufthansa flight."

NOOR: "The Lufthansa direct flight departs Cairo at 10:30 AM and arrives
       in Berlin at 2:45 PM. It's 340 euros for economy class, and the
       flight is about 4 hours and 15 minutes. Shall I select this one?"
```

**Judging criteria hit:**
- Visual precision: Reading flight details from a complex UI
- Beyond text box: Voice-driven, no typing needed
- Context-aware: Remembers the search context through multi-turn
- Live: Real-time narration during processing

### Scenario 2: "Read me this news article" (≈60 seconds)

**Demonstrates:** Page comprehension, content summarization, image description, intelligent content filtering.

```
USER: "Go to BBC News and read me the top story."

NOOR: "Opening BBC News now."
       [NavigatorAgent: navigate to bbc.com/news]

NOOR: "I'm on the BBC News homepage. The main story has a large photo of
       [describes image]. The headline reads: [headline]. Let me open it
       and read it for you."
       [ScreenVisionAgent: analyze, find top story]
       [NavigatorAgent: click headline]

NOOR: "Here's the article. [Reads headline]. The article reports that...
       [3-4 sentence summary of key points]. Would you like me to read
       the full article, or shall we look at other news?"
```

**Judging criteria hit:**
- Multimodal: Image description + text reading
- Smart summarization: Skips ads, navigation, cookie banners
- Natural flow: Feels like a human reading companion

### Scenario 3: "Fill out a form for me" (≈60 seconds)

**Demonstrates:** Form field identification, bidirectional voice interaction, confirmation loop.

```
USER: "I need to sign up for a website. Can you help me fill in a registration form?"

NOOR: "Of course! Let me navigate to the sign-up page. What website?"

USER: "GitHub."

NOOR: "Opening GitHub's sign-up page."
       [NavigatorAgent: navigate to github.com/signup]

NOOR: "I can see the GitHub sign-up form. There are four fields:
       First is email address. What's your email?"

USER: "ali@example.com"

NOOR: "Got it. I've entered ali@example.com in the email field.
       Next field is password. Go ahead."

USER: [speaks password]

NOOR: "Password entered. The next field asks for a username. What username
       would you like?"

[... continues through form ...]

NOOR: "All fields are filled in. I can see a green checkmark next to each
       field, which means everything looks good. There's a 'Create account'
       button at the bottom. Shall I click it?"
```

**Judging criteria hit:**
- Accessibility: Voice-guided form completion
- Visual precision: Reading form labels, detecting validation states
- Two-way conversation: Back-and-forth for each field
- Color awareness: "green checkmark" — info screen readers miss

---

## 6.3 — DEMO VIDEO SCRIPT (`docs/demo_script.md`)

Total length: **≤4 minutes**

```
[0:00-0:30] INTRO & PROBLEM
- Title card: "Noor — Your Eyes on the Web"
- Voiceover: "2.2 billion people worldwide have a vision impairment.
  The web was built for sighted users. Traditional screen readers
  parse HTML tags — they break on modern web apps, fail on images,
  and require expert-level keyboard shortcuts."
- Quick shots: screen reader struggling with a dynamic site

[0:30-0:45] SOLUTION
- "Noor is different. She doesn't read HTML — she SEES the screen,
  using Gemini's multimodal vision to understand web pages the way
  a sighted person would."
- Show architecture diagram briefly

[0:45-2:15] DEMO SCENARIO 1: Flight Search
- Live recording of Noor navigating Google Flights
- Voice interaction visible in transcript panel
- Show the screenshot → Gemini vision → action pipeline

[2:15-3:15] DEMO SCENARIO 2: News Reading
- Live recording of Noor reading BBC News
- Highlight image description capability
- Show content summarization

[3:15-3:45] DEMO SCENARIO 3: Form Filling (abbreviated)
- Quick demonstration of form field interaction
- Show bidirectional voice conversation

[3:45-4:00] CLOSING
- Architecture diagram: ADK multi-agent → Gemini → Cloud Run
- "Noor: Because everyone deserves an internet that talks back."
- Tech stack callout: Google ADK, Gemini Live API, Vertex AI, Cloud Run
```

---

## 6.4 — ARCHITECTURE DIAGRAM

Create a clear architecture diagram for the submission. This should be a PNG/SVG added to the Devpost image carousel.

### Diagram Content

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER (Voice)                                │
│                    🎤 Microphone / 🔊 Speaker                       │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ WebSocket (PCM Audio)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CLIENT (Browser)                                  │
│              Accessible HTML/JS + AudioWorklet                       │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ WebSocket
                              ▼
┌═════════════════════════════════════════════════════════════════════┐
│                    GOOGLE CLOUD RUN                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  FastAPI Server                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │  ADK Multi-Agent System                                  │ │  │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │ │  │
│  │  │  │ScreenVision  │ │ Navigator    │ │PageSummarizer  │  │ │  │
│  │  │  │Agent         │ │ Agent        │ │Agent           │  │ │  │
│  │  │  └──────┬───────┘ └──────┬───────┘ └───────┬────────┘  │ │  │
│  │  │         │                │                  │           │ │  │
│  │  │  ┌──────┴────────────────┴──────────────────┴────────┐  │ │  │
│  │  │  │           NoorOrchestrator (Root Agent)            │  │ │  │
│  │  │  └────────────────────────┬───────────────────────────┘  │ │  │
│  │  └───────────────────────────┼──────────────────────────────┘ │  │
│  │                              │                                │  │
│  │  ┌───────────────┐   ┌──────┴───────┐   ┌────────────────┐  │  │
│  │  │ Playwright     │   │ Gemini Live  │   │ Firestore      │  │  │
│  │  │ (Chromium)     │   │ API Stream   │   │ (User Data)    │  │  │
│  │  └───────────────┘   └──────────────┘   └────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└═══════════════════════════════════╤══════════════════════════════════┘
                                    │
                                    ▼
┌═════════════════════════════════════════════════════════════════════┐
│                    VERTEX AI                                        │
│  ┌────────────────┐   ┌───────────────────┐   ┌────────────────┐  │
│  │ Gemini 2.5      │   │ Gemini Live API   │   │ Cloud Logging  │  │
│  │ Flash (Vision)  │   │ (Streaming Audio) │   │ & Monitoring   │  │
│  └────────────────┘   └───────────────────┘   └────────────────┘  │
└═════════════════════════════════════════════════════════════════════┘
```

**Tool:** Create this diagram using draw.io, Excalidraw, or any diagramming tool. Export as PNG at 1920x1080 for the Devpost image carousel.

---

## 6.5 — SUBMISSION CHECKLIST (Devpost Requirements)

Every item below is **required** unless marked [BONUS]:

### Required Deliverables

- [ ] **Category selection:** UI Navigator ☸️
- [ ] **Text description:** Summary of features, tech used, data sources, learnings
- [ ] **Public GitHub repository URL** with:
  - [ ] Complete source code
  - [ ] `README.md` with spin-up instructions (step-by-step)
  - [ ] `CLAUDE.md` governance file
  - [ ] `ARCHITECTURE.md` with architecture diagram
  - [ ] `.env.example` for environment configuration
  - [ ] `requirements.txt` or `pyproject.toml` for dependencies
- [ ] **Proof of GCP deployment:**
  - [ ] Screen recording of Cloud Run console showing running service, OR
  - [ ] Link to `infra/` Terraform files + `scripts/deploy.sh`
- [ ] **Architecture diagram:** PNG in image carousel (clear, readable)
- [ ] **Demo video:** ≤4 minutes, uploaded to YouTube (public), showing:
  - [ ] Real working software (no mockups)
  - [ ] Multimodal/agentic features in real-time
  - [ ] Problem statement + solution value pitch

### Bonus Deliverables

- [ ] **[BONUS +0.6] Blog post:** Published on dev.to or Medium
  - Include #GeminiLiveAgentChallenge hashtag
  - Include "created for the Gemini Live Agent Challenge hackathon" disclosure
  - Cover: how Noor was built with Gemini + Google Cloud
- [ ] **[BONUS +0.2] Automated deployment:** Terraform config in `infra/`
- [ ] **[BONUS +0.2] GDG membership:** Link to public GDG profile

---

## 6.6 — README.md TEMPLATE

```markdown
# Noor — Your Eyes on the Web 🌟

> AI-powered web navigator for visually impaired users, built with Google ADK and Gemini.

**Hackathon:** Gemini Live Agent Challenge | **Category:** UI Navigator ☸️

## What is Noor?

Noor (نور — "Light" in Arabic) is an AI assistant that gives visually impaired
users independent access to the web through natural voice conversation. Unlike
traditional screen readers that parse HTML, Noor uses Gemini's multimodal vision
to *see* the screen — understanding visual hierarchy, interpreting images, and
navigating any website regardless of its accessibility markup.

## Features

- **Voice-First Interaction:** Natural conversation via Gemini Live API with barge-in support
- **Visual Screen Comprehension:** Gemini multimodal vision analyzes screenshots to understand page layout
- **Autonomous Navigation:** Clicks, types, scrolls, and navigates based on voice commands
- **Smart Content Reading:** Summarizes articles, reads search results, describes images
- **Form Assistance:** Guides users through form fields with voice prompts
- **Cookie Banner Dismissal:** Automatically detects and offers to dismiss cookie popups

## Tech Stack

- **Google ADK** — Multi-agent orchestration
- **Gemini 2.5 Flash** — Multimodal vision + language
- **Gemini Live API** — Real-time bidirectional audio streaming
- **Playwright** — Headless Chromium browser automation
- **Cloud Run** — Containerized backend hosting
- **Vertex AI** — Gemini model serving
- **Firestore** — User preferences and session data
- **Terraform** — Infrastructure-as-code deployment

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud account with billing enabled
- Gemini API key (for local dev) or GCP project with Vertex AI enabled

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/noor.git
   cd noor
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your Gemini API key
   ```

5. Run the application:
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port 8080
   ```

6. Open http://localhost:8080 in your browser.

### Cloud Deployment

```bash
# Set your GCP project
export GOOGLE_CLOUD_PROJECT=your-project-id

# Run initial setup
bash scripts/setup_gcp.sh

# Deploy with Terraform
cd infra && terraform init && terraform apply

# Or deploy directly
bash scripts/deploy.sh
```

## Architecture

[Architecture diagram here]

## Demo Video

[YouTube link here]

## Blog Post

[Blog link here] — Created for the Gemini Live Agent Challenge hackathon.

## Team

- [Your Name] — [Role]

## License

Apache 2.0
```

---

## 6.7 — IMPLEMENTATION ORDER

1. **Integration tests** — Verify full pipeline end-to-end
2. **Bug fixes** — Address issues found in integration testing
3. **Demo scenario polish** — Practice each scenario, tune agent prompts for reliability
4. **Architecture diagram** — Create clear PNG
5. **Demo video recording** — Record ≤4 minutes
6. **GCP deployment proof** — Record Cloud Run console
7. **README.md** — Complete with spin-up instructions
8. **Blog post** — Write and publish on dev.to
9. **GDG signup** — Register and get profile link
10. **Devpost submission** — Submit all deliverables

---

## 6.8 — PROMPT TUNING FOR DEMO RELIABILITY

The demo scenarios must work reliably on camera. Here are tuning strategies:

### Pre-Navigation for Speed
For the demo, consider pre-navigating to specific pages or using cached screenshots to reduce latency during recording. The video should show real software, but you can warm up the browser before recording.

### Agent Instruction Tuning
If agents are producing verbose or off-topic responses, tighten the instruction prompts:
- Add "Keep your response to 2-3 sentences" for narration
- Add "Do not explain what tools you are using" for sub-agents
- Add "Respond conversationally, not technically" for the orchestrator

### Fallback Strategies
- If coordinate-clicking fails, the navigator falls back to text-based clicking
- If vision analysis returns incomplete JSON, re-prompt with a simpler instruction
- If Live API streaming is unreliable, use the text WebSocket endpoint for demo

---

## 6.9 — FINAL ACCEPTANCE CRITERIA

- [ ] All 3 demo scenarios complete successfully end-to-end
- [ ] Voice interaction works with <3 second response latency
- [ ] Application deployed and accessible on Cloud Run
- [ ] Architecture diagram is clear and professional
- [ ] Demo video is ≤4 minutes and shows real working software
- [ ] README has complete spin-up instructions
- [ ] Terraform `terraform apply` provisions all resources
- [ ] Blog post published with #GeminiLiveAgentChallenge hashtag
- [ ] GDG profile linked
- [ ] All Devpost submission fields completed
- [ ] GitHub repository is public with all code

---

## 6.10 — POST-SUBMISSION NOTES

After submitting on March 16, 2026:
- **Do NOT modify the code** after the submission deadline
- The judging period runs March 17 – April 3, 2026
- Winners announced at Google Cloud NEXT 2026 (April 22-24)
- Keep the Cloud Run service running through the judging period
- Monitor costs — set up billing alerts in GCP Console
