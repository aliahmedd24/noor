# CLAUDE.md — Noor Project Governance

> This file governs how Claude Code operates on the Noor codebase.
> Read this ENTIRE file before writing or modifying any code.

---

## Project Overview

Noor (نور — "Light" in Arabic) is an AI-powered web navigation agent for visually impaired users. It gives blind users independent access to the web through natural voice conversation and real-time screen comprehension.

**Hackathon:** Gemini Live Agent Challenge (Devpost)
**Category:** UI Navigator ☸️
**Deadline:** March 16, 2026 @ 5:00 PM PDT
**Mandatory Tech:** Gemini multimodal + Google ADK + ≥1 GCP service

**Core differentiator:** Unlike screen readers that parse DOM, Noor uses Gemini multimodal vision to *see* the screen — understanding visual hierarchy, interpreting images, navigating any website regardless of accessibility markup, and narrating every action to keep the user informed.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Language | Python 3.11+ | async/await everywhere |
| Agent Framework | Google ADK (`google-adk`) | Multi-agent orchestration |
| LLM — Vision/Language | Gemini 2.5 Flash (Vertex AI) | Screenshot analysis, page summarization |
| LLM — Streaming Voice | Gemini Live API (via ADK Streaming) | Real-time bidirectional audio |
| Browser | Playwright (async Python) | Headless Chromium / system Edge |
| Server | FastAPI | WebSocket transport, REST health checks |
| Frontend | Vanilla HTML/JS | Accessibility-first, minimal |
| Compute | Google Cloud Run | Containerized backend |
| AI Platform | Vertex AI | Gemini model serving |
| Database | Firestore | User preferences, session history |
| Secrets | Google Secret Manager | API keys, credentials |
| Monitoring | Cloud Logging + Cloud Monitoring | Structured JSON logs |
| IaC | Terraform | Automated GCP provisioning |
| Container | Docker | Reproducible builds |

---

## Architecture

```
NoorOrchestrator (root LlmAgent)
├── ScreenVisionAgent (LlmAgent) — screenshot analysis, element identification
├── NavigatorAgent (LlmAgent) — browser action planning and execution
└── PageSummarizerAgent (LlmAgent) — content extraction, article reading
```

All four agents are ADK `LlmAgent` instances using `gemini-2.5-flash`. The Orchestrator delegates to sub-agents via LLM-driven delegation (ADK reads each sub-agent's `description` field to route). Sub-agents communicate through ADK shared session state using `output_key`.

---

## Architecture Rules

1. All agents MUST be defined using Google ADK primitives (`LlmAgent`, `SequentialAgent`, `ParallelAgent`, or custom `BaseAgent` subclasses).
2. The root agent MUST be exported from `src/agents/__init__.py` as `root_agent` — this is the ADK convention and the framework will not find the agent otherwise.
3. All tools MUST be plain Python functions with comprehensive docstrings. ADK uses the function name, type hints, and docstring to present tools to the LLM. The docstring IS the tool's API documentation for the model.
4. Agent-to-agent communication MUST use ADK shared session state (`output_key` on the sender + `{state_key}` template variables in the receiver's instructions) — NOT direct function calls between agents.
5. Browser automation MUST go through Playwright async API — no Selenium, no Puppeteer, no raw CDP calls.
6. All Gemini API calls for vision analysis MUST use `google-genai` SDK (`from google import genai`). Use Vertex AI in production (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`), Google AI Studio in local dev (`FALSE`).
7. Voice streaming MUST use ADK Streaming with `LiveRequestQueue` and `runner.run_live()` — not raw WebSocket connections to the Live API.
8. All GCP interactions MUST use official Google Cloud Python client libraries.

---

## CRITICAL: Browser / Playwright / Windows Rules

The BrowserManager (`src/browser/manager.py`) implements a **3-strategy launch system** to work reliably across Windows, WSL2, and Linux containers. These rules are NON-NEGOTIABLE.

### Launch Strategy Priority

| Priority | Strategy | Env Var | When |
|----------|----------|---------|------|
| 1 | CDP Connect | `NOOR_CDP_ENDPOINT` | Attach to externally-launched browser |
| 2 | System Browser Channel | `NOOR_BROWSER_CHANNEL` | **Windows/macOS local dev** — uses Edge/Chrome |
| 3 | Bundled Playwright Chromium | *(default)* | **Docker / Cloud Run / CI** |

### Hard Rules

- On Windows local dev: Set `NOOR_BROWSER_CHANNEL=msedge` in `.env`. Do NOT run `playwright install chromium` on Windows — it will fail or cause version mismatch issues.
- `playwright install chromium --with-deps` is ONLY executed inside the Dockerfile for the Linux container build. It must NEVER appear in any Windows setup instructions, scripts, or Makefiles.
- Every entry point (`src/main.py`, `tests/conftest.py`, standalone scripts) MUST set the Windows-compatible asyncio event loop policy before any async code:
  ```python
  import sys
  if sys.platform == "win32":
      import asyncio
      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
  ```
- ALL `chromium.launch()` calls MUST include these args: `["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]`. These prevent crashes in containers, WSL2, and headless environments.
- All Playwright usage MUST use the async API (`playwright.async_api`) — never `playwright.sync_api`.
- When the launch strategy is CDP (`connect_over_cdp`), the `stop()` method must NOT close the browser — we don't own that process.
- On total launch failure, the error message MUST include Windows-specific troubleshooting steps.

---

## Code Style

- **Python:** PEP 8, type hints on all function signatures, `async`/`await` for all I/O.
- **Models:** Pydantic v2 for all structured data (scene descriptions, action plans, user preferences, API responses).
- **Docstrings:** Google style with `Args:`, `Returns:`, `Raises:` sections.
- **Logging:** `structlog` with JSON output for Cloud Logging compatibility. Import logger per module: `logger = structlog.get_logger(__name__)`.
- **Error handling:** Custom exceptions in `src/utils/errors.py`. Never use bare `except:`. Tool functions must catch exceptions internally and return `{"status": "error", "error": "message"}` — never let exceptions propagate to the agent layer.
- **Imports:** Group as stdlib → third-party → local, separated by blank lines. Use absolute imports from `src.*`.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Production | `""` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Production | `us-central1` | GCP region |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | `FALSE` | `TRUE` for Vertex AI (prod), `FALSE` for AI Studio (dev) |
| `GOOGLE_API_KEY` | Dev only | `""` | Gemini API key (when VERTEXAI=FALSE) |
| `FIRESTORE_DATABASE` | No | `(default)` | Firestore database ID |
| `NOOR_LOG_LEVEL` | No | `INFO` | Logging level |
| `NOOR_BROWSER_HEADLESS` | No | `true` | Browser headless mode |
| `NOOR_BROWSER_CHANNEL` | **Windows: Yes** | `""` | System browser: `msedge` or `chrome`. REQUIRED on Windows. Leave empty for Docker. |
| `NOOR_CDP_ENDPOINT` | No | `""` | CDP URL (e.g., `http://localhost:9222`). Optional fallback. |
| `NOOR_HOST` | No | `0.0.0.0` | Server bind host |
| `NOOR_PORT` | No | `8080` | Server bind port |
| `NOOR_STREAMING_MODE` | No | `true` | Enable Gemini Live API streaming |

---

## Project Structure

```
noor/
├── CLAUDE.md                          # THIS FILE — governance rules
├── ARCHITECTURE.md                    # System architecture documentation
├── README.md                          # Project overview + spin-up instructions
├── .env.example                       # Environment variable template
├── pyproject.toml                     # Python project config
├── requirements.txt                   # Pinned dependencies
├── Dockerfile                         # Production container
├── docker-compose.yml                 # Local development stack
│
├── infra/                             # Terraform IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── cloud_run.tf
│   ├── firestore.tf
│   └── secrets.tf
│
├── src/
│   ├── __init__.py
│   ├── main.py                        # FastAPI entrypoint + WebSocket server
│   ├── config.py                      # Settings from env vars (Pydantic)
│   │
│   ├── agents/                        # ADK Agent definitions
│   │   ├── __init__.py                # MUST export root_agent
│   │   ├── agent.py                   # Root agent assembly
│   │   ├── orchestrator.py            # NoorOrchestrator — root LLM agent
│   │   ├── vision_agent.py            # ScreenVisionAgent
│   │   ├── navigator_agent.py         # NavigatorAgent
│   │   ├── summarizer_agent.py        # PageSummarizerAgent
│   │   └── instructions/              # System prompts (text files)
│   │       ├── orchestrator.txt
│   │       ├── vision.txt
│   │       ├── navigator.txt
│   │       └── summarizer.txt
│   │
│   ├── tools/                         # ADK Tool functions
│   │   ├── __init__.py
│   │   ├── browser_tools.py           # navigate, click, type, scroll, screenshot
│   │   ├── vision_tools.py            # analyze_current_page, describe_page_aloud, find_and_click
│   │   ├── page_tools.py              # Content extraction
│   │   └── user_tools.py              # User preferences (Firestore)
│   │
│   ├── browser/                       # Playwright browser automation
│   │   ├── __init__.py
│   │   ├── manager.py                 # BrowserManager — multi-strategy launch
│   │   ├── actions.py                 # Click, type, scroll, navigate, wait
│   │   └── screenshot.py              # Screenshot capture + grid overlay
│   │
│   ├── vision/                        # Gemini multimodal vision
│   │   ├── __init__.py
│   │   ├── analyzer.py                # ScreenAnalyzer — Gemini vision calls
│   │   └── models.py                  # SceneDescription, PageElement, BoundingBox
│   │
│   ├── voice/                         # Voice interface
│   │   ├── __init__.py
│   │   ├── streaming.py               # ADK LiveRequestQueue integration
│   │   └── persona.py                 # Noor voice config (voice, language)
│   │
│   ├── storage/                       # Persistence
│   │   ├── __init__.py
│   │   ├── firestore_client.py        # Firestore CRUD
│   │   └── session_store.py           # Session state persistence
│   │
│   └── utils/                         # Shared utilities
│       ├── __init__.py
│       ├── logging.py                 # structlog setup
│       └── errors.py                  # Custom exceptions
│
├── client/                            # Frontend
│   ├── index.html                     # Accessible UI shell
│   ├── styles.css                     # High-contrast accessible CSS
│   ├── app.js                         # WebSocket + audio client
│   └── audio.js                       # AudioWorklet for mic/speaker
│
├── tests/
│   ├── conftest.py                    # Shared fixtures, Windows asyncio fix
│   ├── test_browser_tools.py
│   ├── test_vision_analysis.py
│   ├── test_agent_orchestration.py
│   └── eval/                          # ADK evaluation sets
│       ├── navigation_eval.json
│       └── summarization_eval.json
│
├── scripts/
│   ├── setup_gcp.sh                   # GCP project bootstrap
│   ├── deploy.sh                      # Build + deploy to Cloud Run
│   └── demo_scenarios.py              # Pre-scripted demo scenarios
│
└── docs/
    ├── architecture_diagram.png
    ├── gcp_proof_recording.md
    └── demo_script.md
```

---

## File Conventions

- Agent instruction prompts go in `src/agents/instructions/*.txt` and are loaded at import time via `Path(__file__).parent / "instructions" / "name.txt"`.
- Tools are grouped by domain in `src/tools/`. Each tool function MUST have a docstring that starts with a one-line summary (ADK reads this to decide when to invoke the tool).
- Pydantic models go in the relevant module's `models.py` file.
- The `src/agents/__init__.py` file MUST export `root_agent`. This is the ADK convention — the framework locates agents by this name.
- All `__init__.py` files must exist (even if empty) so the Python package structure is valid.

---

## ADK Tool Function Contract

Every function registered as an ADK tool MUST follow this contract:

```python
async def tool_name(param1: str, param2: int = 0) -> dict:
    """One-line summary of what this tool does.

    Detailed description of when and how to use this tool.
    Include examples if helpful for the LLM.

    Args:
        param1: Description of param1.
        param2: Description of param2. Default: 0.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - [other relevant keys]
        - error: Error message if status is 'error', None otherwise
    """
    try:
        # ... implementation ...
        return {"status": "success", ...}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

Rules:
- Use only simple types for parameters: `str`, `int`, `float`, `bool`, `list`, `dict`.
- ALWAYS return a dict with a `status` key.
- NEVER raise exceptions — catch them and return `{"status": "error", "error": "..."}`.
- The docstring is the ONLY documentation the LLM sees. Be thorough.

---

## Agent Session State Keys

Agents communicate via shared session state. These are the established keys:

| Key | Writer | Reader | Type | Purpose |
|-----|--------|--------|------|---------|
| `vision_analysis` | ScreenVisionAgent | NavigatorAgent, PageSummarizerAgent, Orchestrator | str | Last vision analysis result |
| `navigation_result` | NavigatorAgent | Orchestrator | str | Result of last browser action |
| `page_summary` | PageSummarizerAgent | Orchestrator | str | Last content summary |
| `current_url` | browser tools | All | str | Current page URL |
| `current_title` | browser tools | All | str | Current page title |

---

## Gemini API Usage

### Vision Analysis (non-streaming)

```python
from google import genai
from google.genai import types

client = genai.Client()
response = await client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=[
        types.Content(parts=[
            types.Part.from_image(image=types.Image(image_bytes=jpeg_bytes, mime_type="image/jpeg")),
            types.Part.from_text(prompt),
        ])
    ],
    config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=4096,
        response_mime_type="application/json",
    )
)
```

- Use `response_mime_type="application/json"` to force structured JSON output.
- Low temperature (0.1) for consistent element identification.
- Parse with Pydantic: `SceneDescription.model_validate_json(response.text)`.
- Screenshots MUST be JPEG format with mime_type `"image/jpeg"`.

### Streaming Voice (via ADK)

```python
from google.adk.runners import Runner
from google.adk.streaming import LiveRequestQueue

live_queue = LiveRequestQueue()
async for event in runner.run_live(session=session, live_request_queue=live_queue):
    # Handle audio/text events
```

- The root agent's model is set to the Live API model (`gemini-live-2.5-flash-native-audio`) in streaming mode.
- Sub-agents still use standard `gemini-2.5-flash` for tool calls — ADK handles this transparently.

---

## Viewport & Coordinate System

All screenshots are captured at a fixed **1280×800 pixel** viewport. All vision prompts and coordinate references use this exact dimension. Changing viewport size requires updating:
- `BrowserManager.DEFAULT_VIEWPORT_WIDTH` / `DEFAULT_VIEWPORT_HEIGHT`
- All vision prompt templates in `src/agents/instructions/vision.txt`
- All tool docstrings that reference coordinate ranges

Coordinate origin `(0, 0)` is the **top-left corner**. X increases rightward (0–1280), Y increases downward (0–800).

---

## Testing

- Framework: `pytest` with `pytest-asyncio` (mode: `auto`).
- `tests/conftest.py` MUST set `WindowsSelectorEventLoopPolicy` on Windows before any fixtures.
- Browser tests use the shared `browser` fixture which respects `NOOR_BROWSER_CHANNEL` from `.env`.
- ADK agent evaluation uses `.evalset.json` files in `tests/eval/` run via `adk eval`.
- All tests must pass with `NOOR_BROWSER_CHANNEL=msedge` on Windows and without it in Docker.

---

## Deployment

- `Dockerfile` uses `playwright install chromium --with-deps` (handles all system dependencies automatically).
- `playwright install chromium` is ONLY executed inside Docker — NEVER on Windows.
- Cloud Run: min-instances=0, max-instances=5, memory=2Gi, cpu=2, session-affinity=true (for WebSocket).
- Terraform in `infra/` provisions all GCP resources (Cloud Run, Firestore, IAM, Artifact Registry).
- `scripts/deploy.sh` builds the Docker image, pushes to Artifact Registry, and deploys to Cloud Run.
- `scripts/setup_gcp.sh` enables APIs and creates the service account with required IAM roles.

---

## Key Constraints

- This is a hackathon project — optimize for **demo quality** over production hardening.
- The demo video is ≤4 minutes — focus on 3 compelling scenarios (flight search, news reading, form filling).
- UI Navigator category requires: Gemini multimodal interpreting screenshots → outputting executable browser actions.
- Judges may NOT run the project — the video, code, and architecture diagram must tell the story.
- The project must be NEW — no reuse of prior work.
- All submission materials must be in English.

---

## Quick Reference: Common Commands

```bash
# Local dev (Windows)
pip install -e ".[dev]"
# Do NOT run: playwright install chromium
cp .env.example .env  # Then set NOOR_BROWSER_CHANNEL=msedge and GOOGLE_API_KEY
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload

# Run tests
pytest tests/ -v

# ADK dev UI (text-based agent testing)
adk run src/agents

# ADK streaming dev UI (voice testing)
adk web src/agents --streaming

# Docker build + run
docker build -t noor .
docker run -p 8080:8080 --env-file .env noor

# Deploy to Cloud Run
bash scripts/deploy.sh

# Terraform
cd infra && terraform init && terraform plan && terraform apply
```
