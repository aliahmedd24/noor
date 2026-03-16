# Noor — Your Eyes on the Web

**AI-powered web navigator for visually impaired users.**

Noor (Arabic for "Light") gives blind users independent access to the web through natural voice conversation and real-time screen comprehension. Unlike screen readers that parse HTML, Noor uses Gemini multimodal vision to *see* the screen — understanding visual hierarchy, interpreting images, and navigating any website regardless of accessibility markup.

**Hackathon:** Gemini Live Agent Challenge | **Category:** UI Navigator

---

## Architecture

```
User (Voice/Text)
    |
    v
Accessible Client UI (HTML/JS, ES Modules, WCAG 2.1 AA)
    |  WebSocket (bidi-streaming)
    v
FastAPI Server (Cloud Run, CORS, GZip, Security Headers)
    |
    v
NoorOrchestrator (ADK root_agent, BuiltInPlanner)
    |-- ScreenVisionAgent    (Gemini vision — screenshot analysis)
    |-- NavigatorAgent       (Playwright — browser automation)
    |-- PageSummarizerAgent  (Content extraction + summarization)
    |
    +-- Gemini Live API (bidirectional streaming audio)
    +-- Playwright Chromium (headless browser, 1280x800 viewport)
    +-- Vertex AI / AI Studio (model serving)
```

**4 ADK agents**, each with a single responsibility:
- **Orchestrator** — routes user intent, plans multi-step actions, narrates results
- **Vision** — captures and analyzes screenshots with Gemini multimodal
- **Navigator** — clicks, types, scrolls, navigates via Playwright
- **Summarizer** — extracts and summarizes page content for audio delivery

Agents communicate via **structured session state** (`output_key` + `output_schema` with Pydantic models).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | Google ADK (`google-adk`) |
| LLM — Vision/Language | Gemini 2.5 Flash (Vertex AI) |
| LLM — Streaming Voice | Gemini Live API (ADK Streaming) |
| Browser | Playwright (async Python, headless Chromium) |
| Server | FastAPI + WebSocket |
| Frontend | Vanilla HTML/JS ES Modules (accessibility-first) |
| Compute | Google Cloud Run |
| AI Platform | Vertex AI |
| Database | Firestore |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Observability | Cloud Trace + Cloud Logging |

---

## Frontend

The client is a **zero-dependency vanilla JS** application built with ES modules. No build step required.

**Features:**
- **Chat-bubble transcript** — user messages right-aligned, Noor left-aligned, tool activity spinners
- **Voice interaction** — pulsing mic button with real-time waveform visualization
- **Live screenshot panel** — shows what Noor sees with bounding-box annotation overlays
- **Onboarding overlay** — first-visit guide with example prompt chips
- **Settings panel** — voice speed, text size, dark/light theme (persisted via localStorage)
- **Toast notifications** — connection status, errors with retry actions
- **WCAG 2.1 AA** — skip-nav, landmark regions, ARIA live regions, focus management, keyboard shortcuts, `prefers-reduced-motion` support
- **Responsive** — desktop two-column layout, mobile single-column with collapsible screenshot panel

**Keyboard shortcuts:**
- `Space` — toggle microphone (when no input is focused)
- `Escape` — close modals/settings
- `Tab` — navigate all interactive elements

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
- Microsoft Edge or Google Chrome (Windows/macOS) OR Docker

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/noor.git
cd noor
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set:
```
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

**Windows users:** Set `NOOR_BROWSER_CHANNEL=msedge` (already set in `.env.example`). Do **NOT** run `playwright install chromium` on Windows.

**Linux/macOS/Docker:** Leave `NOOR_BROWSER_CHANNEL` empty and run `playwright install chromium --with-deps`.

### 3. Run with ADK CLI (text mode)

```bash
adk run noor_agent
```

### 4. Run with ADK Web UI

```bash
# Text mode
adk web noor_agent

# Voice + video streaming
adk web noor_agent --streaming
```

### 5. Run with custom server (full UI)

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

Open http://localhost:8080 in your browser.

---

## Running Tests

### Unit tests (no API key needed)

```bash
pytest tests/test_agent_orchestration.py -v
```

Tests agent hierarchy, definitions, callbacks, tool wiring, prompts, and state helpers.

### Integration tests (requires API key + browser)

```bash
pytest tests/test_agents.py -v
```

Tests full agent behavior: greeting, navigation, vision, search flows, error handling.

### ADK evaluation

```bash
# Via CLI
adk eval noor_agent tests/eval/navigation_eval.test.json \
    --config_file_path tests/eval/test_config.json \
    --print_detailed_results

# Via pytest
pytest tests/test_eval.py -v
```

Evaluates tool trajectory correctness (IN_ORDER matching, threshold 0.8) and response quality.

### All tests

```bash
pytest tests/ -v
```

---

## Docker

```bash
docker build -t noor .
docker run -p 8080:8080 --env-file .env noor
```

The Dockerfile uses a **multi-stage build** with a non-root user and `HEALTHCHECK`. Playwright Chromium is installed only inside the container — never on Windows dev machines.

---

## GCP Deployment

### Pre-flight check

```bash
./scripts/preflight.sh
```

Validates environment variables, CLI tools, GCP authentication, API enablement, and Docker availability.

### Option A: Automated deploy script (recommended)

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
./scripts/deploy.sh
```

Runs pre-flight checks, tries ADK CLI deploy, falls back to `gcloud run deploy` if needed.

### Option B: ADK CLI direct

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
    --source=. \
    --region=us-central1 \
    --allow-unauthenticated \
    --memory=2Gi --cpu=2 \
    --min-instances=1 \
    --timeout=300 \
    --session-affinity
```

### CI/CD (GitHub Actions)

- **CI** (`.github/workflows/ci.yml`): Runs on push/PR to `main`. Lints with ruff, runs pytest, verifies Docker build.
- **Deploy** (`.github/workflows/deploy.yml`): Runs on tag push (`v*`) or manual dispatch. Authenticates via Workload Identity Federation, pushes to Artifact Registry, deploys to Cloud Run with `--min-instances=1` (no cold starts for demo).

### Infrastructure (Terraform)

```bash
cd infra && terraform init && terraform apply
```

Provisions: Firestore, IAM, Cloud Run service, Artifact Registry, API enablement, monitoring.

---

## Project Structure

```
noor/
├── noor_agent/              # ADK agent package (adk run/web/deploy target)
│   ├── __init__.py          # from . import agent
│   ├── agent.py             # root_agent + App with compaction/resumability
│   ├── prompts.py           # All instruction strings (extracted)
│   ├── orchestrator.py      # NoorOrchestrator (root, BuiltInPlanner)
│   ├── vision_agent.py      # ScreenVisionAgent
│   ├── navigator_agent.py   # NavigatorAgent
│   ├── summarizer_agent.py  # PageSummarizerAgent
│   ├── schemas.py           # Pydantic output schemas
│   ├── callbacks.py         # Agent lifecycle callbacks + UI event emission
│   ├── plugins.py           # ADK plugins (ReflectAndRetry, Logging)
│   ├── state_helpers.py     # State minification for instruction injection
│   ├── tools/               # ADK tool functions
│   │   ├── browser_tools.py # navigate, click, type, scroll, screenshot
│   │   ├── vision_tools.py  # analyze_current_page, describe_page_aloud
│   │   ├── page_tools.py    # extract_page_text, get_page_metadata
│   │   └── state_tools.py   # get_state_detail
│   ├── browser/             # Playwright automation engine
│   │   ├── manager.py       # BrowserManager (3-strategy launch)
│   │   ├── actions.py       # Click, type, scroll, navigate, wait
│   │   ├── screenshot.py    # Screenshot + coordinate grid overlay
│   │   └── service.py       # BrowserService (DI singleton)
│   └── vision/              # Gemini multimodal pipeline
│       ├── analyzer.py      # ScreenAnalyzer (Gemini vision calls)
│       └── models.py        # SceneDescription, PageElement, BoundingBox
├── server/                  # FastAPI server (WebSocket streaming)
│   ├── main.py              # App + bidi-streaming + CORS + security headers
│   ├── config.py            # Pydantic Settings
│   └── persona.py           # Noor voice configuration
├── client/                  # Frontend (accessibility-first, zero-dependency)
│   ├── index.html           # Semantic HTML with skip-nav + landmark regions
│   ├── app.js               # Main entry: WebSocket, components, keyboard shortcuts
│   ├── styles.css            # Design system: dark/light themes, responsive, a11y
│   ├── components/
│   │   ├── transcript.js    # Chat-bubble conversation panel
│   │   ├── mic-button.js    # Mic toggle + pulse + waveform
│   │   ├── screenshot.js    # Live screenshot panel + annotations
│   │   ├── toast.js         # Toast notifications
│   │   ├── onboarding.js    # First-visit overlay
│   │   └── settings.js      # Preferences panel
│   └── assets/
│       └── noor-logo.svg    # Branding
├── tests/
│   ├── conftest.py          # InMemoryRunner fixtures, browser fixture
│   ├── test_agent_orchestration.py  # Agent hierarchy + definition tests
│   ├── test_agents.py       # Agent behavior tests (InMemoryRunner)
│   ├── test_eval.py         # ADK AgentEvaluator wrapper
│   └── eval/
│       ├── navigation_eval.test.json    # Navigation eval cases
│       ├── summarization_eval.test.json # Summarization eval cases
│       └── test_config.json             # Eval criteria + thresholds
├── infra/                   # Terraform
│   ├── main.tf              # Provider + API enablement
│   ├── variables.tf         # project_id, region
│   ├── iam.tf               # Service account + IAM bindings
│   ├── firestore.tf         # Firestore database
│   ├── artifact_registry.tf # Docker image registry
│   ├── cloud_run.tf         # Cloud Run service + public access
│   └── outputs.tf           # service_account, cloud_run_url, registry
├── scripts/
│   ├── preflight.sh         # Pre-deployment validation
│   ├── deploy.sh            # ADK deploy with fallback
│   └── setup_gcp.sh         # GCP API enablement
├── .github/workflows/
│   ├── ci.yml               # Lint + test + Docker build
│   └── deploy.yml           # Build, push, deploy to Cloud Run
├── CLAUDE.md                # Project governance
├── pyproject.toml           # Python project config
├── Dockerfile               # Multi-stage, non-root, HEALTHCHECK
├── .dockerignore            # Exclude tests, docs, .env
├── .env.example             # Environment variable template
└── README.md                # This file
```

---

## Demo Scenarios

### 1. Flight Search
> "Find me cheap flights from Cairo to Berlin for next Friday."

Noor navigates to Google Flights, fills in the form, reads results with prices and times.

### 2. News Reading
> "Go to BBC News and read me the top story."

Noor opens BBC, describes the page with image descriptions, reads and summarizes the article.

### 3. Form Filling
> "Help me sign up for GitHub."

Noor opens the signup page, identifies form fields, and guides the user field-by-field with voice interaction.

---

## Key Design Decisions

- **Vision-first, not DOM-first**: Gemini analyzes screenshots instead of parsing HTML, making Noor work on any website regardless of accessibility markup.
- **Voice-native**: Gemini Live API provides real-time bidirectional audio — no TTS/STT pipeline needed.
- **Always narrate**: Every action is spoken aloud. The user is never left wondering what's happening.
- **Structured agent communication**: Pydantic `output_schema` + `output_key` for typed data flow between agents — never free text.
- **BuiltInPlanner with thinking**: The orchestrator uses Gemini's native thinking (budget: 2048 tokens) to plan multi-step actions before executing.
- **Zero-dependency frontend**: Vanilla JS with ES modules — no build step, no bundler, no node_modules.
- **Live screenshot streaming**: Vision tool results include base64 screenshots forwarded to the client via WebSocket UI events.

---

## License

Built for the Gemini Live Agent Challenge hackathon.
