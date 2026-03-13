# PHASE 0: PROJECT FOUNDATION & ENVIRONMENT SETUP

## Project: Noor — AI-Powered Web Navigator for Visually Impaired Users

### Hackathon Context

- **Hackathon:** Gemini Live Agent Challenge (Devpost)
- **Category:** UI Navigator ☸️
- **Deadline:** March 16, 2026 @ 5:00 PM PDT
- **Mandatory Tech:** Gemini multimodal + Google GenAI SDK or ADK + ≥1 GCP service
- **Prize Target:** Grand Prize ($25K) + Best UI Navigator ($10K) + subcategory prizes

---

## 0.1 — PROJECT IDENTITY

**Name:** Noor (نور — "Light" in Arabic)
**Tagline:** "Your eyes on the web."
**One-liner:** An AI agent that gives visually impaired users independent access to the web through natural voice conversation and real-time screen comprehension.

**Core Differentiator:** Unlike screen readers that parse DOM, Noor uses Gemini multimodal vision to *see* the screen like a sighted human assistant — understanding visual hierarchy, interpreting images, reading poorly-structured sites, and narrating every action to maintain user awareness.

---

## 0.2 — TECH STACK OVERVIEW

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Agent Framework** | Google ADK (Python) `google-adk` | Multi-agent orchestration, tool management, session state |
| **LLM — Vision/Language** | Gemini 2.5 Flash (via Vertex AI) | Screenshot interpretation, page summarization, action planning |
| **LLM — Streaming Voice** | Gemini Live API (via ADK Streaming) | Real-time bidirectional audio, barge-in, voice persona |
| **Browser Automation** | Playwright (Python async) | Headless Chromium control, screenshots, action execution |
| **Backend Server** | FastAPI (Python async) | WebSocket transport, REST health checks, ADK integration |
| **Frontend Client** | Vanilla HTML/JS (minimal) | Audio capture/playback, WebSocket client, accessibility-first UI |
| **Compute** | Google Cloud Run | Containerized backend deployment |
| **AI Platform** | Vertex AI | Gemini model serving, API management |
| **Database** | Firestore | User preferences, session history, frequently visited sites |
| **Secrets** | Google Secret Manager | API keys, service account credentials |
| **Monitoring** | Cloud Logging + Cloud Monitoring | Observability, error tracking, latency metrics |
| **IaC** | Terraform | Automated GCP resource provisioning (bonus points) |
| **Containerization** | Docker | Reproducible builds, Cloud Run deployment |

---

## 0.3 — PROJECT STRUCTURE

```
noor/
├── CLAUDE.md                          # Claude Code governance file
├── ARCHITECTURE.md                    # System architecture documentation
├── README.md                          # Project overview + spin-up instructions
├── LICENSE                            # Apache 2.0
├── .env.example                       # Environment variable template
├── .gitignore
├── pyproject.toml                     # Python project config (uv/pip)
├── requirements.txt                   # Pinned dependencies
├── Dockerfile                         # Production container
├── docker-compose.yml                 # Local development stack
│
├── infra/                             # Terraform IaC (Phase 5)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── cloud_run.tf
│   ├── firestore.tf
│   ├── secrets.tf
│   └── monitoring.tf
│
├── src/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app entrypoint + WebSocket server
│   ├── config.py                      # Environment config, constants
│   │
│   ├── agents/                        # ADK Agent definitions
│   │   ├── __init__.py                # Exports root_agent
│   │   ├── agent.py                   # Root agent (ADK entry point)
│   │   ├── orchestrator.py            # NoorOrchestrator — root LLM agent
│   │   ├── vision_agent.py            # ScreenVisionAgent — screenshot analysis
│   │   ├── navigator_agent.py         # NavigatorAgent — browser action planning
│   │   ├── summarizer_agent.py        # PageSummarizerAgent — content extraction
│   │   └── instructions/              # Agent system prompts (text files)
│   │       ├── orchestrator.txt
│   │       ├── vision.txt
│   │       ├── navigator.txt
│   │       └── summarizer.txt
│   │
│   ├── tools/                         # ADK Tool definitions
│   │   ├── __init__.py
│   │   ├── browser_tools.py           # Playwright-based tools (navigate, click, type, scroll, screenshot)
│   │   ├── vision_tools.py            # Screenshot capture + Gemini vision analysis
│   │   ├── page_tools.py              # Page content extraction, form field reading
│   │   └── user_tools.py              # User preference read/write (Firestore)
│   │
│   ├── browser/                       # Browser automation engine
│   │   ├── __init__.py
│   │   ├── manager.py                 # BrowserManager — lifecycle, context, page management
│   │   ├── actions.py                 # Action executor — click, type, scroll, navigate, wait
│   │   └── screenshot.py              # Screenshot capture with viewport management
│   │
│   ├── vision/                        # Vision processing pipeline
│   │   ├── __init__.py
│   │   ├── analyzer.py                # ScreenAnalyzer — Gemini multimodal scene description
│   │   └── models.py                  # Pydantic models for scene descriptions
│   │
│   ├── voice/                         # Voice interface layer
│   │   ├── __init__.py
│   │   ├── streaming.py               # ADK Streaming / LiveRequestQueue integration
│   │   └── persona.py                 # Noor voice persona configuration
│   │
│   ├── storage/                       # Persistence layer
│   │   ├── __init__.py
│   │   ├── firestore_client.py        # Firestore operations
│   │   └── session_store.py           # Session state persistence
│   │
│   └── utils/                         # Shared utilities
│       ├── __init__.py
│       ├── logging.py                 # Structured logging setup
│       └── errors.py                  # Custom exception classes
│
├── client/                            # Frontend client
│   ├── index.html                     # Accessible UI shell
│   ├── styles.css                     # Minimal, high-contrast accessible CSS
│   ├── app.js                         # WebSocket client, audio capture/playback
│   └── audio.js                       # AudioWorklet for mic capture + speaker output
│
├── tests/                             # Test suite
│   ├── __init__.py
│   ├── test_browser_tools.py
│   ├── test_vision_analysis.py
│   ├── test_agent_orchestration.py
│   └── eval/                          # ADK evaluation sets
│       ├── navigation_eval.json
│       └── summarization_eval.json
│
├── scripts/                           # Utility scripts
│   ├── setup_gcp.sh                   # GCP project bootstrap
│   ├── deploy.sh                      # Build + deploy to Cloud Run
│   └── demo_scenarios.py              # Pre-scripted demo scenarios for video
│
└── docs/
    ├── architecture_diagram.png       # Submission-ready architecture diagram
    ├── gcp_proof_recording.md         # Instructions for GCP deployment proof
    └── demo_script.md                 # 4-minute demo video script
```

---

## 0.4 — CLAUDE.md GOVERNANCE FILE

Create this file at the project root. It governs how Claude Code operates on this codebase.

```markdown
# CLAUDE.md — Noor Project Governance

## Project Overview
Noor is an AI-powered web navigation agent for visually impaired users, built for the Gemini Live Agent Challenge hackathon. It uses Google ADK for multi-agent orchestration, Gemini Live API for real-time voice interaction, and Gemini multimodal vision for screen comprehension.

## Tech Stack
- **Language:** Python 3.11+
- **Agent Framework:** Google ADK (`google-adk`)
- **LLM:** Gemini 2.5 Flash (Vertex AI) for vision/language, Gemini Live API for streaming audio
- **Browser:** Playwright (async Python)
- **Server:** FastAPI (async, WebSocket support)
- **Frontend:** Vanilla HTML/JS (accessibility-first)
- **Cloud:** GCP (Cloud Run, Vertex AI, Firestore, Secret Manager, Cloud Logging)
- **IaC:** Terraform
- **Container:** Docker

## Architecture Rules
1. All agents MUST be defined using Google ADK primitives (`LlmAgent`, `SequentialAgent`, `ParallelAgent`, or custom `BaseAgent` subclasses)
2. The root agent MUST be exported from `src/agents/__init__.py` as `root_agent` (ADK convention)
3. All tools MUST be plain Python functions with comprehensive docstrings (ADK uses docstrings for tool selection)
4. Agent-to-agent communication MUST use ADK shared session state (`output_key` + `{state_key}` in instructions) — NOT direct function calls
5. Browser automation MUST go through Playwright async API — no Selenium, no puppeteer
6. All Gemini API calls for vision MUST go through Vertex AI (not Google AI Studio) for production readiness
7. Voice streaming MUST use ADK Streaming with `LiveRequestQueue` — not raw WebSocket to Live API
8. All GCP interactions MUST use official Google Cloud Python client libraries

## Code Style
- Python: Follow PEP 8, use type hints everywhere, async/await for all I/O
- Use Pydantic v2 models for all structured data (scene descriptions, action plans, user preferences)
- Docstrings: Google style (Args, Returns, Raises)
- Logging: Use `structlog` with JSON output for Cloud Logging compatibility
- Error handling: Custom exceptions in `src/utils/errors.py`, never bare `except:`

## Environment Variables
- `GOOGLE_CLOUD_PROJECT` — GCP project ID
- `GOOGLE_CLOUD_LOCATION` — GCP region (default: `us-central1`)
- `GOOGLE_GENAI_USE_VERTEXAI` — Set to `TRUE` for Vertex AI, `FALSE` for AI Studio (dev)
- `GOOGLE_API_KEY` — Gemini API key (dev only, when VERTEXAI=FALSE)
- `FIRESTORE_DATABASE` — Firestore database ID (default: `(default)`)
- `NOOR_LOG_LEVEL` — Logging level (default: `INFO`)
- `NOOR_BROWSER_HEADLESS` — Browser headless mode (default: `true`)
- `NOOR_BROWSER_CHANNEL` — System browser channel: `msedge` or `chrome` (REQUIRED on Windows, unset for Docker/Cloud Run)
- `NOOR_CDP_ENDPOINT` — CDP WebSocket URL to attach to a running browser (optional fallback)

## CRITICAL: Browser / Playwright / Windows Rules
- On Windows: Set `NOOR_BROWSER_CHANNEL=msedge` and DO NOT run `playwright install chromium`
- BrowserManager uses a 3-strategy launch: CDP → system channel → bundled Chromium (see Phase 1 PRD)
- `playwright install chromium` is ONLY run inside the Dockerfile, never on the developer's Windows machine
- All entry points (`src/main.py`, `tests/conftest.py`) MUST set `asyncio.WindowsSelectorEventLoopPolicy()` on Windows before any async code runs
- All Playwright calls MUST use async API (`playwright.async_api`) — never sync
- All `chromium.launch()` calls MUST include `--no-sandbox`, `--disable-gpu`, `--disable-dev-shm-usage`

## File Conventions
- Agent instruction prompts go in `src/agents/instructions/*.txt` (loaded at import time)
- Tools are grouped by domain in `src/tools/`
- Each tool function MUST have a docstring that starts with a one-line summary (ADK requirement)
- Pydantic models go in the relevant module's `models.py`

## Testing
- Use `pytest` with `pytest-asyncio` for async tests
- Use ADK's built-in eval framework for agent evaluation
- Browser tests should use Playwright's built-in test fixtures

## Deployment
- Docker builds MUST include Playwright browser binaries (`playwright install chromium --with-deps`)
- `playwright install chromium` is ONLY executed inside Docker — NEVER on Windows dev machines
- Cloud Run service MUST have min-instances=0, max-instances=5, memory=2Gi, cpu=2
- Terraform in `infra/` handles all GCP resource provisioning

## Key Constraints
- This is a hackathon project — optimize for demo quality over production hardening
- The demo video is ≤4 minutes — focus on 3-4 compelling scenarios
- UI Navigator category requires: Gemini multimodal interpreting screenshots → outputting executable actions
- Judges may NOT test the project — the video and code must tell the story
```

---

## 0.5 — INITIAL SETUP TASKS

### Task 0.5.1: Initialize Project

```bash
mkdir noor && cd noor
git init
```

### Task 0.5.2: Create `pyproject.toml`

```toml
[project]
name = "noor"
version = "0.1.0"
description = "AI-powered web navigator for visually impaired users"
requires-python = ">=3.11"
dependencies = [
    "google-adk>=1.0.0",
    "google-cloud-aiplatform>=1.70.0",
    "google-cloud-firestore>=2.19.0",
    "google-cloud-secret-manager>=2.21.0",
    "google-cloud-logging>=3.11.0",
    "google-genai>=1.0.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "websockets>=13.0",
    "playwright>=1.49.0",
    "pydantic>=2.10.0",
    "structlog>=24.4.0",
    "python-dotenv>=1.0.0",
    "Pillow>=11.0.0",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Task 0.5.3: Create `.env.example`

```env
# === GCP Configuration ===
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# === Gemini API (dev mode, when VERTEXAI=FALSE) ===
GOOGLE_API_KEY=your-gemini-api-key

# === Firestore ===
FIRESTORE_DATABASE=(default)

# === Browser Configuration ===
# Strategy 2 (RECOMMENDED FOR WINDOWS): Use system Edge/Chrome — no Chromium download needed
NOOR_BROWSER_CHANNEL=msedge
# Strategy 1 (FALLBACK): Connect to externally-launched browser via CDP
# NOOR_CDP_ENDPOINT=http://localhost:9222
# Strategy 3 (Docker/Cloud Run): Leave both unset to use bundled Playwright Chromium

# === App Configuration ===
NOOR_LOG_LEVEL=INFO
NOOR_BROWSER_HEADLESS=true
NOOR_HOST=0.0.0.0
NOOR_PORT=8080
```

### Task 0.5.4: Create `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium with ALL system dependencies.
# This is the ONLY place Chromium gets installed.
# On Windows dev machines, use NOOR_BROWSER_CHANNEL=msedge instead.
RUN playwright install chromium --with-deps

# Copy application code
COPY src/ ./src/
COPY client/ ./client/

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Task 0.5.5: Create `.gitignore`

```
__pycache__/
*.pyc
.env
.venv/
venv/
*.egg-info/
dist/
build/
.pytest_cache/
.ruff_cache/
node_modules/
.terraform/
*.tfstate
*.tfstate.backup
.terraform.lock.hcl
```

---

## 0.6 — ACCEPTANCE CRITERIA

- [ ] Project directory structure matches the specification above
- [ ] `CLAUDE.md` is present at project root with all governance rules
- [ ] `pyproject.toml` has all dependencies listed
- [ ] `.env.example` documents all required environment variables
- [ ] `Dockerfile` builds successfully with Playwright + Chromium
- [ ] `git init` completed, `.gitignore` configured
- [ ] All `__init__.py` files created (even if empty) so Python package structure is valid
- [ ] Running `pip install -e .` in a venv succeeds without errors

---

## 0.7 — NOTES FOR CLAUDE CODE

- Start by creating the full directory structure and all `__init__.py` files
- Create `CLAUDE.md` first — it governs all subsequent development
- Use `uv` or `pip` — both work, but `pip` is safer for Cloud Run compatibility
- The `src/agents/__init__.py` MUST export `root_agent` — this is the ADK convention
- Playwright install requires running `playwright install chromium` after pip install
- For local development, set `GOOGLE_GENAI_USE_VERTEXAI=FALSE` and use a Gemini API key
- For production/Cloud Run, set `GOOGLE_GENAI_USE_VERTEXAI=TRUE` and use service account auth
