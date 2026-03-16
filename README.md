# Noor — Your Eyes on the Web

**AI-powered web navigator for visually impaired users.**

Noor (Arabic for "Light") gives blind users independent access to the web through natural voice conversation and real-time screen comprehension. Unlike screen readers that parse HTML, Noor uses Gemini multimodal vision to *see* the screen — understanding visual hierarchy, interpreting images, and navigating any website regardless of accessibility markup.

**Hackathon:** Gemini Live Agent Challenge | **Category:** UI Navigator

---

## How It Works

```
                          +-----------------------+
                          |     User (Voice)      |
                          +-----------+-----------+
                                      |
                           WebSocket (bidi audio)
                                      |
                          +-----------v-----------+
                          |  Accessible Client UI |
                          |  (HTML/JS, WCAG 2.1)  |
                          +-----------+-----------+
                                      |
                       WebSocket (PCM audio + JSON)
                                      |
                          +-----------v-----------+
                          |    FastAPI Server      |
                          |  (Cloud Run, 8080)     |
                          +-----------+-----------+
                                      |
                    +-----------------+-----------------+
                    |                                   |
          +---------v----------+             +----------v----------+
          |   Text Runner      |             |  Streaming Runner   |
          | (run_async)        |             | (run_live)          |
          +---------+----------+             +----------+----------+
                    |                                   |
          +---------v----------+             +----------v----------+
          |  NoorTaskLoop      |             |  NoorOrchestrator   |
          |  (LoopAgent x10)   |             |  (LlmAgent direct)  |
          +--------+-----------+             +----------+----------+
                   |                                    |
          +--------v-----------+                        |
          |  NoorOrchestrator  |<-----------------------+
          |  (15 tools)        |
          +---+------+-----+--+
              |      |     |
     +--------+  +---+  +--+--------+
     |           |       |           |
  Gemini    Playwright  Gemini     ADK
  Vision    (Edge/     Live API   Session
  (3.1 Pro) Chromium)  (native    State
                        audio)
```

**What Noor does:**
1. User speaks naturally ("Find me flights from Cairo to Berlin")
2. Noor understands intent via Gemini Live API (real-time bidirectional audio)
3. Opens a browser, navigates to the right website
4. Reads the page using accessibility tree + Gemini vision
5. Fills forms, clicks buttons, scrolls, reads results
6. Narrates every action aloud so the user stays in control

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Agent Framework | Google ADK v1.26 | Multi-agent orchestration, streaming, eval |
| LLM — Text/Vision | Gemini 3.1 Pro (Vertex AI) | Page analysis, task planning, tool use |
| LLM — Voice | Gemini Live API (native audio) | Real-time bidirectional speech |
| Browser | Playwright (async Python) | Headless Edge/Chromium, 1280x800 viewport |
| Server | FastAPI | WebSocket bidi-streaming + REST |
| Frontend | Vanilla HTML/JS | Accessibility-first, zero build step |
| Compute | Google Cloud Run | Containerized deployment |
| AI Platform | Vertex AI | Model serving (global + us-central1) |
| Database | Firestore | Session history, user preferences |
| IaC | Terraform | Firestore, IAM, Cloud Run, Artifact Registry |
| CI/CD | GitHub Actions | Lint, test, deploy on tag push |
| Observability | Cloud Trace + Logging | Via `--trace_to_cloud` |

---

## Agent Architecture

Noor uses a **single orchestrator with 15 tools** rather than a multi-agent hierarchy. This gives the LLM direct access to all capabilities without routing overhead.

```
NoorTaskLoop (LoopAgent, max_iterations=10)            [text mode]
└── NoorOrchestrator (LlmAgent, gemini-3.1-pro, BuiltInPlanner)
    ├── Navigation:  navigate_to_url, click_element_by_text, find_and_click,
    │                type_into_field, select_dropdown_option, fill_form,
    │                scroll_down, scroll_up, go_back_in_browser
    ├── Perception:  analyze_current_page, get_accessibility_tree,
    │                extract_page_text, read_page_aloud
    └── Control:     explain_what_happened, task_complete

NoorOrchestrator (LlmAgent, gemini-live-native-audio)  [voice mode]
└── Same 15 tools, no LoopAgent (Live API doesn't support it),
    no planner (native-audio models don't support thinking)
```

**Two-layer perception:**
- **Layer 1 — Accessibility Tree** (fast, <1s): `get_accessibility_tree` returns ARIA roles, labels, values for every interactive element. This is the primary sense.
- **Layer 2 — Vision Analysis** (slow, ~30s): `analyze_current_page` takes a screenshot and uses Gemini multimodal to describe visual layout, images, and spatial relationships.

**Dual-model architecture:**
- Text model (`gemini-3.1-pro`) runs on `global` endpoint
- Live API model (`gemini-live-2.5-flash-native-audio`) requires `us-central1`
- A custom `_RegionalLiveGemini` subclass routes Live API calls to the regional endpoint

---

## Frontend

Zero-dependency vanilla JS with ES modules. No build step.

- **Chat-bubble transcript** — user and Noor messages, tool activity spinners
- **Voice interaction** — pulsing mic button with waveform visualization
- **Live browser feed** — real-time 2 FPS JPEG stream of what the browser sees
- **Onboarding overlay** — first-visit guide with example prompts
- **Settings** — voice speed, text size, dark/light theme (localStorage)
- **WCAG 2.1 AA** — skip-nav, landmark regions, ARIA live regions, focus management, keyboard shortcuts, `prefers-reduced-motion`
- **Responsive** — desktop two-column (chat + browser), mobile single-column

**Keyboard shortcuts:** `Space` toggle mic | `Escape` close modals | `Tab` navigate

---

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud project with Vertex AI enabled
- Microsoft Edge or Google Chrome (Windows/macOS) OR Docker

### 1. Clone and install

```bash
git clone https://github.com/AibrahimEA/noor.git
cd noor
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

Authenticate:
```bash
gcloud auth application-default login
```

**Windows:** Set `NOOR_BROWSER_CHANNEL=msedge`. Do **not** run `playwright install chromium`.
**Linux/Docker:** Leave `NOOR_BROWSER_CHANNEL` empty. Run `playwright install chromium --with-deps`.

### 3. Run

```bash
# ADK terminal (text)
adk run noor_agent

# ADK web UI (text + voice)
adk web noor_agent --streaming

# Custom server (full UI with live browser feed)
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

Open http://localhost:8080

---

## Testing

```bash
# Unit tests (no API key needed)
pytest tests/test_agent_orchestration.py -v

# Integration tests (requires API key + browser)
pytest tests/test_agents.py -v

# ADK evaluation (tool trajectory matching)
adk eval noor_agent tests/eval/navigation_eval.test.json \
    --config_file_path tests/eval/test_config.json

# All tests
pytest tests/ -v
```

---

## Docker

```bash
docker build -t noor .
docker run -p 8080:8080 --env-file .env noor

# Or with docker-compose
docker compose up
```

Multi-stage build, non-root user, `HEALTHCHECK`. Playwright Chromium installed only inside the container.

---

## Deployment

### Option A: Automated deploy (recommended)

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
./scripts/deploy.sh
```

### Option B: ADK CLI

```bash
adk deploy cloud_run \
    --project=$GOOGLE_CLOUD_PROJECT \
    --region=$GOOGLE_CLOUD_LOCATION \
    --service_name=noor-agent \
    --app_name=noor \
    --trace_to_cloud \
    noor_agent
```

### Option C: Docker + gcloud

```bash
gcloud run deploy noor-agent \
    --source=. --region=us-central1 \
    --allow-unauthenticated \
    --memory=2Gi --cpu=2 \
    --session-affinity
```

### Infrastructure (Terraform)

```bash
cd infra && terraform init && terraform apply
```

Provisions Firestore, IAM, Cloud Run, Artifact Registry, and API enablement.

---

## Project Structure

```
noor/
├── noor_agent/                 # ADK agent package
│   ├── __init__.py             # ADK discovery (from . import agent)
│   ├── agent.py                # root_agent, streaming_root_agent, App
│   ├── orchestrator.py         # NoorOrchestrator (LlmAgent + 15 tools)
│   ├── prompts.py              # All instruction strings
│   ├── schemas.py              # Pydantic output schemas
│   ├── callbacks.py            # Lifecycle callbacks + overlay dismissal
│   ├── plugins.py              # ADK plugins
│   ├── state_helpers.py        # State minification
│   ├── vision_agent.py         # ScreenVisionAgent (sub-agent)
│   ├── navigator_agent.py      # NavigatorAgent (sub-agent)
│   ├── summarizer_agent.py     # PageSummarizerAgent (sub-agent)
│   ├── tools/
│   │   ├── browser_tools.py    # navigate, click, type, scroll, fill_form
│   │   ├── vision_tools.py     # analyze_current_page, find_and_click
│   │   ├── page_tools.py       # get_accessibility_tree, extract_page_text
│   │   ├── state_tools.py      # task_complete, explain_what_happened
│   │   └── user_tools.py       # User preferences
│   ├── browser/
│   │   ├── manager.py          # BrowserManager (3-strategy launch)
│   │   ├── actions.py          # Click, type, scroll, navigate
│   │   ├── screenshot.py       # Screenshot + coordinate grid
│   │   ├── service.py          # BrowserService singleton
│   │   └── stealth.py          # Anti-detection + cookie auto-dismiss
│   └── vision/
│       ├── analyzer.py         # Gemini multimodal vision calls
│       └── models.py           # SceneDescription, PageElement
├── server/
│   ├── main.py                 # FastAPI + bidi-streaming + screen stream
│   ├── config.py               # Pydantic Settings
│   └── persona.py              # Voice configuration
├── client/
│   ├── index.html              # Accessible semantic HTML
│   ├── app.js                  # WebSocket, components, keyboard shortcuts
│   ├── audio.js                # AudioWorklet for PCM capture
│   ├── styles.css              # Dark/light themes, responsive
│   ├── components/             # transcript, mic-button, screenshot, etc.
│   └── assets/noor-logo.svg
├── tests/
│   ├── conftest.py             # Fixtures (InMemoryRunner, browser)
│   ├── test_agent_orchestration.py
│   ├── test_agents.py
│   ├── test_eval.py
│   └── eval/                   # ADK .test.json evaluation cases
├── infra/                      # Terraform (Firestore, IAM, Cloud Run)
├── scripts/                    # deploy.sh, setup_gcp.sh, preflight.sh
├── .github/workflows/          # CI + deploy
├── Dockerfile                  # Multi-stage, non-root, HEALTHCHECK
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── CLAUDE.md                   # Project governance (for AI assistants)
```

---

## Demo Scenarios

### 1. Flight Search (~90s)
> "Find me cheap flights from Cairo to Berlin for next Friday."

Noor navigates to Google Flights, reads the accessibility tree to find form fields, fills departure/destination/date, searches, and reads results with prices and times.

### 2. News Reading (~60s)
> "Go to BBC News and read me the top story."

Noor opens BBC, auto-dismisses cookie banners, describes the homepage layout, clicks the top story, and reads the full article.

### 3. Form Filling (~90s)
> "Help me sign up for GitHub."

Noor opens the signup page, reads all form fields via accessibility tree, and guides the user through each field with voice interaction.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Vision-first, not DOM-first | Gemini analyzes screenshots — works on any site regardless of a11y markup |
| Accessibility tree as primary sense | `get_accessibility_tree` is fast (<1s) and gives structured form/button data |
| Voice-native | Gemini Live API = real-time bidi audio, no separate TTS/STT |
| Always narrate | Every action is spoken. The user is never left in silence. |
| Single orchestrator with all tools | Simpler than multi-agent routing; LLM picks the right tool directly |
| Dual-model routing | Text model on `global`, Live API on `us-central1` via custom Gemini subclass |
| Zero-dependency frontend | Vanilla JS, no build step, no bundler, no node_modules |
| Stealth by default | Anti-detection JS + cookie auto-dismiss so sites don't block the agent |

---

## License

Built for the Gemini Live Agent Challenge hackathon.
