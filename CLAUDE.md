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
| Agent Framework | Google ADK (`google-adk`) | Multi-agent orchestration, streaming, eval |
| LLM — Vision/Language | Gemini 2.5 Flash (Vertex AI) | Screenshot analysis, page summarization |
| LLM — Streaming Voice | Gemini Live API (via ADK Streaming) | Real-time bidirectional audio |
| Browser | Playwright (async Python) | Headless Chromium / system Edge |
| Server | FastAPI | WebSocket transport, REST health checks |
| Frontend | Vanilla HTML/JS | Accessibility-first, minimal |
| Compute | Google Cloud Run | Via `adk deploy cloud_run` |
| AI Platform | Vertex AI | Gemini model serving |
| Observability | Cloud Trace | Via `--trace_to_cloud` flag |
| Database | Firestore | User preferences, session history |
| IaC | Terraform | Firestore, IAM, monitoring (non-ADK resources) |

---

## Architecture

```
NoorOrchestrator (root Agent, BuiltInPlanner with thinking_budget=2048)
├── ScreenVisionAgent (Agent, output_key="vision_result", output_schema=VisionResult)
├── NavigatorAgent (Agent, output_key="nav_result", output_schema=NavigationResult)
└── PageSummarizerAgent (Agent, output_key="page_summary", output_schema=PageSummary)
```

The Orchestrator delegates to sub-agents via **LLM-driven Auto-Flow** (ADK reads each sub-agent's `description` field to route). Sub-agents communicate through **ADK shared session state** using `output_key` + `output_schema` (Pydantic models) for structured, typed data flow — never free text.

The root agent uses `BuiltInPlanner` with Gemini's native thinking to plan multi-step actions before executing.

The agent is wrapped in an `App` object with `EventsCompactionConfig` (summarizes every 5 invocations) and `ResumabilityConfig` for long conversations.

---

## ADK Design Rules

These rules come directly from the ADK skill guide and are NON-NEGOTIABLE.

1. **Every agent package MUST have `__init__.py`** that imports the agent module: `from . import agent`
2. **Entry point MUST be `root_agent`** — a module-level variable in `agent.py`. Not `agent`, not `my_agent`, not `ROOT_AGENT`.
3. **One agent = one responsibility.** Split agents with 5+ tools into specialists.
4. **Use `output_key` + `output_schema`** (Pydantic) for reliable data flow between agents — not free text.
5. **Set `max_iterations` on every `LoopAgent`.** No exceptions.
6. **Write precise sub-agent `description` fields** — they drive Auto-Flow routing decisions.
7. **Extract prompts to `prompts.py`** — never inline large instruction strings in agent definitions.
8. All tools MUST be plain Python functions with type hints + comprehensive docstrings. ADK uses the function name, type hints, and docstring to present tools to the LLM.
9. **Never use global variables for state** — use `tool_context.state` or `callback_context.state`.
10. Browser automation MUST go through Playwright async API — no Selenium, no Puppeteer.
11. Voice streaming MUST use ADK Streaming with `LiveRequestQueue` + `runner.run_live()` + `RunConfig(StreamingMode.BIDI)`.
12. All GCP interactions MUST use official Google Cloud Python client libraries.

---

## CRITICAL: Browser / Playwright / Windows Rules

The BrowserManager (`noor_agent/browser/manager.py`) implements a **3-strategy launch system**. These rules are NON-NEGOTIABLE.

| Priority | Strategy | Env Var | When |
|----------|----------|---------|------|
| 1 | CDP Connect | `NOOR_CDP_ENDPOINT` | Attach to externally-launched browser |
| 2 | System Browser Channel | `NOOR_BROWSER_CHANNEL` | **Windows/macOS local dev** — uses Edge/Chrome |
| 3 | Bundled Playwright Chromium | *(default)* | **Docker / Cloud Run / CI** |

### Hard Rules

- On Windows: Set `NOOR_BROWSER_CHANNEL=msedge` in `.env`. Do NOT run `playwright install chromium` on Windows.
- `playwright install chromium --with-deps` is ONLY executed inside the Dockerfile. NEVER on Windows.
- Every entry point (`server/main.py`, `tests/conftest.py`) MUST set the Windows asyncio policy before any async code:
  ```python
  import sys
  if sys.platform == "win32":
      import asyncio
      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
  ```
- ALL `chromium.launch()` calls MUST include: `["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]`.
- All Playwright MUST use async API (`playwright.async_api`) — never sync.
- CDP strategy: `stop()` must NOT close the browser — we don't own that process.

---

## Code Style

- **Python:** PEP 8, type hints on all function signatures, `async`/`await` for all I/O.
- **Models:** Pydantic v2 for all structured data — especially `output_schema` on agents.
- **Docstrings:** Google style with `Args:`, `Returns:`, `Raises:`.
- **Logging:** `structlog` with JSON output. Import per module: `logger = structlog.get_logger(__name__)`.
- **Error handling:** Tool functions MUST catch exceptions internally and return `{"status": "error", "error": "..."}` — never raise.
- **Imports:** stdlib → third-party → local. Use relative imports within `noor_agent/` package.
- **Line length:** 100 characters. **Linter:** `ruff`.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Production | `""` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Production | `us-central1` | GCP region |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | `FALSE` | `TRUE` for Vertex AI (prod), `FALSE` for AI Studio (dev) |
| `GOOGLE_API_KEY` | Dev only | `""` | Gemini API key (when VERTEXAI=FALSE) |
| `NOOR_LOG_LEVEL` | No | `INFO` | Logging level |
| `NOOR_BROWSER_HEADLESS` | No | `true` | Browser headless mode |
| `NOOR_BROWSER_CHANNEL` | **Windows: Yes** | `""` | `msedge` or `chrome`. REQUIRED on Windows. Empty for Docker. |
| `NOOR_CDP_ENDPOINT` | No | `""` | CDP URL (e.g., `http://localhost:9222`). |
| `NOOR_HOST` | No | `0.0.0.0` | Server bind host |
| `NOOR_PORT` | No | `8080` | Server bind port |
| `NOOR_STREAMING_MODE` | No | `true` | Enable Gemini Live API streaming |

---

## Project Structure

```
noor/                                  # Project root
├── CLAUDE.md                          # THIS FILE
├── README.md                          # Project overview + spin-up instructions
├── ARCHITECTURE.md                    # System architecture doc
├── pyproject.toml                     # Python project config
├── requirements.txt                   # Pinned dependencies
├── Dockerfile                         # Production container (Playwright + Chromium)
├── .env.example                       # Environment variable template
├── .env                               # Local environment (gitignored)
│
├── noor_agent/                        # ADK agent package (adk run/web/deploy target)
│   ├── __init__.py                    # MUST contain: from . import agent
│   ├── agent.py                       # MUST define root_agent at module level
│   ├── prompts.py                     # All instruction strings (extracted, not inline)
│   ├── orchestrator.py                # NoorOrchestrator agent definition
│   ├── vision_agent.py                # ScreenVisionAgent definition
│   ├── navigator_agent.py             # NavigatorAgent definition
│   ├── summarizer_agent.py            # PageSummarizerAgent definition
│   ├── callbacks.py                   # Agent lifecycle callbacks
│   │
│   ├── tools/                         # ADK Tool functions
│   │   ├── __init__.py
│   │   ├── browser_tools.py           # navigate, click, type, scroll, screenshot
│   │   ├── vision_tools.py            # analyze_current_page, describe_page_aloud, find_and_click
│   │   └── user_tools.py              # User preferences
│   │
│   ├── browser/                       # Playwright browser automation
│   │   ├── __init__.py
│   │   ├── manager.py                 # BrowserManager — 3-strategy launch
│   │   ├── actions.py                 # Click, type, scroll, navigate, wait
│   │   └── screenshot.py              # Screenshot capture + grid overlay
│   │
│   └── vision/                        # Gemini multimodal vision pipeline
│       ├── __init__.py
│       ├── analyzer.py                # ScreenAnalyzer — Gemini vision calls
│       └── models.py                  # VisionResult, NavigationResult, PageSummary, SceneDescription
│
├── server/                            # FastAPI server (separate from agent package)
│   ├── __init__.py
│   ├── main.py                        # FastAPI app + bidi-streaming WebSocket
│   ├── config.py                      # Pydantic settings from env vars
│   └── persona.py                     # Noor voice configuration
│
├── client/                            # Frontend (accessibility-first)
│   ├── index.html
│   ├── styles.css
│   └── app.js
│
├── tests/
│   ├── conftest.py                    # InMemoryRunner fixtures, Windows asyncio fix
│   ├── test_browser.py                # Browser automation tests
│   ├── test_vision.py                 # Vision analysis tests
│   ├── test_agents.py                 # Agent tests via InMemoryRunner
│   ├── test_eval.py                   # ADK AgentEvaluator wrapper
│   └── eval/
│       ├── navigation.test.json       # ADK eval cases (tool trajectory)
│       └── test_config.json           # Eval criteria thresholds
│
├── scripts/
│   ├── setup_gcp.sh                   # GCP API enablement + Terraform
│   └── deploy.sh                      # adk deploy cloud_run wrapper
│
└── infra/                             # Terraform (Firestore, IAM, monitoring only)
    ├── main.tf
    ├── variables.tf
    ├── iam.tf
    ├── firestore.tf
    └── outputs.tf
```

### Why `noor_agent/` is separate from `server/`

ADK CLI commands (`adk run`, `adk web`, `adk deploy cloud_run`) target the **agent package directory** — the one containing `__init__.py` + `agent.py` with `root_agent`. The FastAPI server in `server/` is a custom wrapper for the bidi-streaming WebSocket endpoint. They are separate concerns:

- `adk run noor_agent` — runs the agent in terminal mode (text)
- `adk web noor_agent` — runs the ADK dev UI (text + streaming)
- `adk web noor_agent --streaming` — runs with voice/video
- `uvicorn server.main:app` — runs the custom FastAPI server with accessible client UI

---

## File Conventions

- **`noor_agent/__init__.py`** MUST contain `from . import agent` — ADK discovers agents through this.
- **`noor_agent/agent.py`** MUST define `root_agent` at module level.
- **Prompts** go in `noor_agent/prompts.py` as named string constants — never inline in agent definitions.
- **Tools** are grouped by domain in `noor_agent/tools/`. Each tool function MUST have a docstring starting with a one-line summary.
- **Pydantic models** for `output_schema` go in `noor_agent/vision/models.py`.
- **Callbacks** go in `noor_agent/callbacks.py`.

---

## ADK Tool Function Contract

Every function registered as an ADK tool MUST follow this contract:

```python
def tool_name(param1: str, param2: int = 0) -> dict:
    """One-line summary of what this tool does.

    Detailed description of when and how to use this tool.

    Args:
        param1: Description.
        param2: Description. Default: 0.

    Returns:
        dict with status key ('success' or 'error') plus result data.
    """
    try:
        # ... implementation ...
        return {"status": "success", ...}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

Rules:
- Simple types only for parameters: `str`, `int`, `float`, `bool`, `list`, `dict`.
- Add `tool_context: ToolContext` parameter when you need state access.
- ALWAYS return a dict with a `status` key.
- NEVER raise exceptions — catch and return error dict.
- The docstring is the ONLY thing the LLM sees. Be thorough.

---

## Structured Inter-Agent Data Flow

Sub-agents use `output_schema` (Pydantic) + `output_key` for typed state communication:

```python
from pydantic import BaseModel

class VisionResult(BaseModel):
    page_type: str
    summary: str
    interactive_elements: list[dict]
    primary_action: str
    has_cookie_banner: bool
    has_modal: bool

vision_agent = Agent(
    name="screen_vision",
    output_schema=VisionResult,
    output_key="vision_result",
    # ...
)
```

### Session State Keys

| Key | Writer (`output_key`) | Reader | Pydantic Model | Purpose |
|-----|----------------------|--------|---------------|---------|
| `vision_result` | ScreenVisionAgent | NavigatorAgent, Orchestrator | `VisionResult` | Last screenshot analysis |
| `nav_result` | NavigatorAgent | Orchestrator | `NavigationResult` | Last browser action result |
| `page_summary` | PageSummarizerAgent | Orchestrator | `PageSummary` | Last content summary |
| `pages_visited` | callbacks | All | `list[str]` | URLs visited in session |
| `actions_taken` | callbacks | All | `int` | Total tool calls count |
| `last_tool` | after_tool_callback | All | `str` | Name of last tool called |

---

## Agent Callbacks

```python
# noor_agent/callbacks.py

def before_agent_init(callback_context):
    """Initialize session state with defaults on first invocation."""
    callback_context.state.setdefault("pages_visited", [])
    callback_context.state.setdefault("actions_taken", 0)
    callback_context.state.setdefault("errors", [])

def after_tool_log(tool, args, tool_context, result) -> dict | None:
    """Log every tool execution for narration context and debugging."""
    tool_context.state["last_tool"] = tool.name
    tool_context.state["last_tool_result"] = str(result)[:500]
    tool_context.state["actions_taken"] = tool_context.state.get("actions_taken", 0) + 1
    return None  # Proceed normally (return dict to override result)
```

Callback rules:
- Return `None` → proceed normally.
- Return a value → short-circuit (skip the tool/model/agent call).
- Use `before_tool_callback` for input validation and guardrails.
- Use `after_tool_callback` for logging and result post-processing.
- Use `before_agent_callback` for state initialization.

---

## Streaming Architecture (Bidi-Demo Pattern)

The server follows the **canonical ADK bidi-demo pattern** exactly:

```
Phase 1 (App Init):     Agent + SessionService + Runner — created once at startup
Phase 2 (Session Init): Per WebSocket: get_or_create session → RunConfig(BIDI) → LiveRequestQueue
Phase 3 (Streaming):    Concurrent upstream (client→queue) + downstream (run_live→client)
Phase 4 (Termination):  live_request_queue.close() in finally block
```

Key rules:
- **One `LiveRequestQueue` per session.** Never reuse across sessions.
- **`RunConfig(streaming_mode=StreamingMode.BIDI)`** with `input_audio_transcription`, `output_audio_transcription`, and `session_resumption` enabled.
- **`asyncio.gather(upstream_task, downstream_task)`** for concurrent bidirectional flow.
- **Always close the queue in `finally`** — even if exceptions occurred.
- Root agent model switches to Live API model (`gemini-live-2.5-flash-native-audio`) in streaming mode. Sub-agents keep `gemini-2.5-flash`.

---

## Gemini API Usage

### Vision Analysis (non-streaming, in sub-agent tools)

```python
from google import genai
from google.genai import types

client = genai.Client()
response = await client.aio.models.generate_content(
    model="gemini-2.5-flash",
    contents=[types.Content(parts=[
        types.Part.from_image(image=types.Image(image_bytes=jpeg_bytes, mime_type="image/jpeg")),
        types.Part.from_text(prompt),
    ])],
    config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=4096,
        response_mime_type="application/json",
    )
)
```

- `response_mime_type="application/json"` forces structured JSON.
- Parse with Pydantic: `SceneDescription.model_validate_json(response.text)`.
- Screenshots MUST be JPEG with `mime_type="image/jpeg"`.

---

## Viewport & Coordinate System

Fixed **1280×800 pixel** viewport. All vision prompts reference these exact dimensions. Origin `(0, 0)` = top-left. X: 0–1280 rightward. Y: 0–800 downward. Changing viewport requires updating `BrowserManager` defaults, all vision prompts, and all tool docstrings.

---

## Testing

### Unit Tests — `InMemoryRunner`

```python
from google.adk.runners import InMemoryRunner
from google.genai import types

runner = InMemoryRunner(agent=root_agent, app_name="noor-test")
session = await runner.session_service.create_session(user_id="test", app_name="noor-test")
content = types.Content(role="user", parts=[types.Part.from_text("Go to google.com")])

events = []
async for event in runner.run_async(user_id="test", session_id=session.id, new_message=content):
    events.append(event)
```

### ADK Evaluation — `.test.json` + `adk eval`

```bash
adk eval noor_agent tests/eval/navigation.test.json --config_file_path tests/eval/test_config.json
```

Eval config uses `tool_trajectory_avg_score` with `IN_ORDER` matching at threshold 0.8.

### All tests must pass with `NOOR_BROWSER_CHANNEL=msedge` on Windows and without it in Docker.

---

## Deployment

### Primary: `adk deploy cloud_run`

```bash
adk deploy cloud_run \
    --project=$GOOGLE_CLOUD_PROJECT \
    --region=$GOOGLE_CLOUD_LOCATION \
    --service_name=noor-agent \
    --app_name=noor \
    --trace_to_cloud \
    noor_agent
```

### Fallback (if Playwright deps need custom Dockerfile):

```bash
gcloud run deploy noor-agent --source=. --region=$GOOGLE_CLOUD_LOCATION --allow-unauthenticated --memory=2Gi --cpu=2 --session-affinity
```

### Supplemental: Terraform for Firestore, IAM, monitoring

```bash
cd infra && terraform init && terraform apply
```

- `playwright install chromium --with-deps` is ONLY in the Dockerfile — NEVER on Windows.
- `--trace_to_cloud` enables Cloud Trace observability automatically.
- Production sessions: swap `InMemorySessionService` → `VertexAiSessionService` or `DatabaseSessionService`.

---

## Key Constraints

- Hackathon project — optimize for **demo quality** over production hardening.
- Demo video ≤ 4 minutes — 3 scenarios: flight search, news reading, form filling.
- UI Navigator category: Gemini multimodal interpreting screenshots → executable browser actions.
- Judges may NOT run the project — video, code, and architecture diagram tell the story.
- Project must be NEW. All submission materials in English.

---

## Quick Reference

```bash
# Local dev (Windows)
pip install -e ".[dev]"
# Do NOT run: playwright install chromium
cp .env.example .env  # Set NOOR_BROWSER_CHANNEL=msedge and GOOGLE_API_KEY

# ADK CLI (targets noor_agent/ package)
adk run noor_agent                    # Terminal mode (text)
adk web noor_agent                    # Dev UI (text)
adk web noor_agent --streaming        # Dev UI (voice + video)

# Custom server
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload

# Tests
pytest tests/ -v
adk eval noor_agent tests/eval/navigation.test.json

# Docker
docker build -t noor .
docker run -p 8080:8080 --env-file .env noor

# Deploy
adk deploy cloud_run --project=$GOOGLE_CLOUD_PROJECT --region=us-central1 --service_name=noor-agent --trace_to_cloud noor_agent

# Terraform (Firestore, IAM, monitoring)
cd infra && terraform init && terraform apply
```

---

## ADK Anti-Patterns to Avoid

1. **Don't use global variables for state** — use `tool_context.state` or `callback_context.state`
2. **Don't create monolithic agents** — split into focused sub-agents (max 4-5 tools each)
3. **Don't skip `__init__.py`** — ADK won't find the agent without `from . import agent`
4. **Don't hardcode API keys** — use `.env` and environment variables
5. **Don't ignore `output_schema`** — use Pydantic models between pipeline stages
6. **Don't nest agent hierarchies deeper than 3-4 levels**
7. **Don't forget `root_agent`** — must be module-level in `agent.py`
8. **Don't put all prompts inline** — extract to `prompts.py`
9. **Don't skip testing** — use `InMemoryRunner` for unit tests, `adk eval` for trajectory eval
10. **Don't reuse `LiveRequestQueue` across sessions** — one per session, close in `finally`
