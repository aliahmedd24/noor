# Noor — System Architecture

> AI-powered web navigator for visually impaired users.

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER (voice / text)                        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    PCM audio (16kHz) + JSON text
                                 │
                    ┌────────────▼────────────┐
                    │   Accessible Client UI  │
                    │  (Vanilla JS, WCAG 2.1) │
                    │                         │
                    │  ┌───────┐ ┌──────────┐ │
                    │  │ Chat  │ │ Browser  │ │
                    │  │Bubbles│ │  Feed    │ │
                    │  │       │ │ (2 FPS)  │ │
                    │  └───────┘ └──────────┘ │
                    └──────┬──────────┬───────┘
                           │          │
               /ws/{uid}/{sid}   /ws-screen/{sid}
              (bidi audio+text)  (JPEG binary)
                           │          │
                    ┌──────▼──────────▼───────┐
                    │      FastAPI Server      │
                    │  ┌──────────────────┐    │
                    │  │   CORS + GZip +  │    │
                    │  │ Security Headers │    │
                    │  └──────────────────┘    │
                    │                          │
                    │  ┌────────┐ ┌─────────┐  │
                    │  │  Text  │ │Streaming│  │
                    │  │ Runner │ │ Runner  │  │
                    │  │(async) │ │ (live)  │  │
                    │  └───┬────┘ └────┬────┘  │
                    └──────┼───────────┼───────┘
                           │           │
              ┌────────────▼───┐ ┌─────▼────────────┐
              │ NoorTaskLoop   │ │ NoorOrchestrator  │
              │ (LoopAgent x10)│ │ (LlmAgent)        │
              │ ┌────────────┐ │ │ gemini-live-2.5-  │
              │ │Orchestrator│ │ │ flash-native-audio│
              │ │gemini-3.1  │ │ │ No planner        │
              │ │-pro-preview│ │ │ 15 tools          │
              │ │BuiltInPlan │ │ └─────────┬─────────┘
              │ │15 tools    │ │           │
              │ └─────┬──────┘ │           │
              └───────┼────────┘           │
                      │                    │
                      └────────┬───────────┘
                               │
            ┌──────────────────▼──────────────────┐
            │            15 Tool Functions         │
            │                                      │
            │  NAVIGATION        PERCEPTION        │
            │  ─────────         ──────────        │
            │  navigate_to_url   get_accessibility_ │
            │  click_element_     tree              │
            │   by_text          analyze_current_   │
            │  find_and_click     page              │
            │  type_into_field   extract_page_text  │
            │  select_dropdown_  read_page_aloud    │
            │   option                              │
            │  fill_form         CONTROL            │
            │  scroll_down/up    ───────            │
            │  go_back_in_       task_complete      │
            │   browser          explain_what_      │
            │                     happened          │
            └──────┬──────────────────┬─────────────┘
                   │                  │
        ┌──────────▼──────┐  ┌────────▼────────┐
        │    Playwright   │  │   Gemini API    │
        │  (async Python) │  │  (Vertex AI)    │
        │                 │  │                 │
        │  Edge/Chromium  │  │  Vision:        │
        │  1280x800       │  │   gemini-3.1-pro│
        │  Stealth mode   │  │   (global)      │
        │  Cookie dismiss │  │                 │
        └─────────────────┘  │  Live Audio:    │
                             │   native-audio  │
                             │   (us-central1) │
                             └─────────────────┘
```

## Streaming Data Flow (Voice Mode)

```
Phase 1 — App Init (startup)
  FastAPI lifespan:
    1. Start BrowserService (Playwright, Edge/Chromium)
    2. Inject into tool modules
    3. Create Text Runner (root_agent) + Streaming Runner (streaming_root_agent)

Phase 2 — Session Init (per WebSocket connection)
    1. Accept WebSocket at /ws/{user_id}/{session_id}
    2. Create/get ADK session
    3. Create LiveRequestQueue (one per session, never reused)
    4. Build RunConfig(BIDI) with speech config + transcription

Phase 3 — Bidi Streaming (concurrent tasks via asyncio.gather)

  ┌─ Upstream Task ──────────────────────────────────────────┐
  │  Client mic → PCM binary frames → live_request_queue     │
  │  Client text → JSON → Content → live_request_queue       │
  └──────────────────────────────────────────────────────────┘

  ┌─ Downstream Task ────────────────────────────────────────┐
  │  streaming_runner.run_live() yields events:              │
  │    - Audio parts → binary WebSocket frame to client      │
  │    - Text parts → JSON WebSocket frame to client         │
  │    - Tool calls → Orchestrator executes tools            │
  │      → Browser actions, vision analysis, etc.            │
  └──────────────────────────────────────────────────────────┘

Phase 4 — Termination
    live_request_queue.close() in finally block
```

## Two-Layer Perception

```
User says: "Search for flights to Berlin"

  Step 1: get_accessibility_tree          ← FAST (<1 second)
  ┌──────────────────────────────────┐
  │ - textbox "Where from?": "Cairo" │   Discovers form fields,
  │ - textbox "Where to?": ""        │   current values, labels
  │ - button "Search"                │
  │ - combobox "Class": "Economy"    │
  └──────────────────────────────────┘

  Step 2: type_into_field(field_label="Where to?", text="Berlin")

  Step 3: get_accessibility_tree          ← Verify it worked
  ┌──────────────────────────────────┐
  │ - textbox "Where to?": "Berlin"  │   ✓ Value updated
  └──────────────────────────────────┘

  Step 4: click_element_by_text("Search")

  Step 5: analyze_current_page            ← SLOW (~30 seconds)
  ┌──────────────────────────────────┐    Only when visual context
  │ Screenshot → Gemini Vision →     │    is needed (images, layout,
  │ "3 flight results shown..."      │    spatial description)
  └──────────────────────────────────┘
```

## Dual-Model Architecture

The text model and Live API model require different Vertex AI endpoints:

```
                    ┌──────────────────┐
                    │  GOOGLE_CLOUD_   │
                    │  LOCATION=global │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │  Gemini 3.1 Pro (text mode) │
              │  BuiltInPlanner (thinking)  │
              │  Temperature: 0.3           │
              └─────────────────────────────┘

                    ┌──────────────────┐
                    │  NOOR_LIVE_API_  │
                    │  LOCATION=       │
                    │  us-central1     │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │  _RegionalLiveGemini        │
              │  (custom Gemini subclass)    │
              │  Overrides _live_api_client  │
              │  to use regional endpoint   │
              │                             │
              │  gemini-live-2.5-flash-     │
              │  native-audio               │
              │  No planner, no thinking    │
              └─────────────────────────────┘
```

## Browser Strategy (3-tier fallback)

| Priority | Strategy | When | Config |
|----------|----------|------|--------|
| 1 | CDP Connect | Attach to external browser | `NOOR_CDP_ENDPOINT=http://localhost:9222` |
| 2 | System Browser | **Windows/macOS local dev** | `NOOR_BROWSER_CHANNEL=msedge` |
| 3 | Bundled Chromium | **Docker / Cloud Run / CI** | Neither env var set |

All strategies launch with: `--no-sandbox --disable-gpu --disable-dev-shm-usage --disable-blink-features=AutomationControlled`

Stealth layer (`browser/stealth.py`) injects anti-detection JS and cookie auto-dismiss scripts into every page and iframe.

## Session State Keys

| Key | Writer | Reader | Purpose |
|-----|--------|--------|---------|
| `current_url` | browser tools | All | Current page URL |
| `current_title` | browser tools | All | Current page title |
| `vision_analysis` | ScreenVisionAgent | Orchestrator | Last screenshot analysis |
| `pages_visited` | callbacks | All | URLs visited in session |
| `actions_taken` | callbacks | All | Total tool calls count |
| `last_tool` | after_tool_callback | All | Name of last tool called |
| `last_tool_error` | after_tool_callback | Orchestrator | Last error for recovery |
| `_ui_events` | callbacks | Server | Queued events for client |

## Live Browser Feed

```
Client                          Server
  │                               │
  ├─── WebSocket CONNECT ────────►│  /ws-screen/{session_id}
  │                               │
  │◄── JPEG binary (2 FPS) ──────┤  BrowserService.take_screenshot()
  │◄── JPEG binary ──────────────┤  quality=50, full_page=false
  │◄── JPEG binary ──────────────┤
  │    ...                        │
  │                               │  Breaks on WebSocket close
  ├─── CLOSE ────────────────────►│  (no send-after-close spam)
```

The client renders frames via `URL.createObjectURL(blob)` with proper cleanup of previous blob URLs.
