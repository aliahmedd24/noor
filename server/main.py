"""
Noor FastAPI Server — Bidi-streaming with ADK Gemini Live API Toolkit.

Architecture follows the official ADK bidi-demo pattern:
- Phase 1 (App Init): Agent, SessionService, Runner created once at startup
- Phase 2 (Session Init): Per-WebSocket: get/create session, RunConfig, LiveRequestQueue
- Phase 3 (Streaming): Concurrent upstream (client->queue) + downstream (run_live->client) tasks
- Phase 4 (Termination): close() the queue on disconnect

Reference: https://github.com/google/adk-samples/tree/main/python/agents/bidi-demo
"""

from dotenv import load_dotenv
load_dotenv()  # MUST be first — ADK reads env vars at import time

import sys
if sys.platform == "win32":
    import asyncio
    # Playwright needs ProactorEventLoop for subprocess support on Windows.
    # Uvicorn's default loop factory forces SelectorEventLoop, which breaks
    # asyncio.create_subprocess_exec(). Override the policy before uvicorn
    # creates its loop, AND patch uvicorn's loop factory as a fallback.
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        import uvicorn.loops.asyncio as _uv_loops
        _orig_factory = _uv_loops.asyncio_loop_factory
        def _proactor_factory(use_subprocess: bool = False):
            return asyncio.ProactorEventLoop
        _uv_loops.asyncio_loop_factory = _proactor_factory
    except Exception:
        pass

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types

from noor_agent.agent import root_agent, streaming_root_agent
from noor_agent.browser.service import get_browser_service
from server.config import settings
from server.persona import build_speech_config

logger = structlog.get_logger(__name__)

# Active screen-stream WebSocket connections (session_id → set of WebSocket)
_screen_subscribers: dict[str, set[WebSocket]] = {}

# ================================================================
# Phase 1: Application Initialization (once at startup)
# ================================================================

APP_NAME = "noor"


def _create_session_service():
    """Create the appropriate session service based on config.

    NOOR_SESSION_BACKEND controls which backend is used:
      - "memory"  (default): InMemorySessionService — local dev
      - "vertex":            VertexAiSessionService — fully managed GCP production
      - "database":          DatabaseSessionService — SQLite or PostgreSQL
    """
    backend = settings.noor_session_backend.lower()

    if backend == "vertex":
        from google.adk.sessions import VertexAiSessionService
        logger.info(
            "session_backend_vertex",
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        return VertexAiSessionService(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

    if backend == "database":
        from google.adk.sessions import DatabaseSessionService
        db_url = "sqlite:///./sessions.db"
        logger.info("session_backend_database", db_url=db_url)
        return DatabaseSessionService(db_url=db_url)

    logger.info("session_backend_memory")
    return InMemorySessionService()


session_service = _create_session_service()

# ADK Runner — text mode (run_async)
runner = Runner(
    app_name=APP_NAME,
    agent=root_agent,
    session_service=session_service,
)

# ADK Runner — streaming mode (run_live with native-audio model)
streaming_runner = Runner(
    app_name=APP_NAME,
    agent=streaming_root_agent,
    session_service=session_service,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start browser eagerly at startup; clean up on shutdown.

    Playwright requires a ProactorEventLoop on Windows to create subprocesses.
    Starting the browser here (on the main uvicorn loop) guarantees the right
    loop type.  If we waited for the agent callback inside ``run_live()``,
    Playwright would fail because the Live API runs on a SelectorEventLoop.
    """
    from noor_agent.browser.service import BrowserService, set_browser_service
    from noor_agent.tools import browser_tools, vision_tools, page_tools

    headless = os.getenv("NOOR_BROWSER_HEADLESS", "true").lower() == "true"
    channel = os.getenv("NOOR_BROWSER_CHANNEL") or None
    cdp_endpoint = os.getenv("NOOR_CDP_ENDPOINT") or None

    service = BrowserService()
    await service.start(headless=headless, channel=channel, cdp_endpoint=cdp_endpoint)
    set_browser_service(service)

    # Inject into tool modules so tools can use the browser immediately
    browser_tools.set_browser_service(service)
    vision_tools.set_browser_service(service)
    page_tools.set_browser_service(service)

    logger.info("browser_started_at_startup", strategy=service.browser.launch_strategy)

    yield

    if service.is_started:
        await service.stop()
        logger.info("browser_stopped")


app = FastAPI(
    title="Noor — Your Eyes on the Web",
    description="AI-powered web navigator for visually impaired users",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
_allowed_origins = ["http://localhost:8080", "http://127.0.0.1:8080"]
if settings.noor_allowed_origins:
    _allowed_origins.extend(
        o.strip() for o in settings.noor_allowed_origins.split(",") if o.strip()
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Gzip compression ──
app.add_middleware(GZipMiddleware, minimum_size=500)


# ── Security headers ──
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Serve client static files with cache headers
app.mount("/static", StaticFiles(directory="client"), name="static")


@app.get("/")
async def index():
    """Serve the accessible client UI."""
    return FileResponse("client/index.html")


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    service = get_browser_service()
    return {
        "status": "healthy",
        "agent": APP_NAME,
        "browser": service is not None and service.is_started,
    }


# ================================================================
# Structured Output → Human Narration
# ================================================================

async def _drain_ui_events(websocket: WebSocket, user_id: str, session_id: str):
    """Forward queued UI events (tool_start, tool_end, screenshot) to client."""
    try:
        sess = await session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id,
        )
        if sess:
            ui_events = sess.state.get("_ui_events", [])
            if ui_events:
                for ui_event in ui_events:
                    await websocket.send_text(json.dumps(ui_event))
                sess.state["_ui_events"] = []
    except Exception:
        pass


def _narrate_structured(obj: dict) -> str | None:
    """Convert sub-agent structured JSON output to spoken narration.

    ADK sub-agents produce structured JSON via output_schema. The orchestrator
    doesn't get another turn to narrate, so we convert server-side.

    Returns a human-readable string, or None if the dict isn't a known schema.
    """
    # NavigationOutput: action_taken, success, current_url, current_title
    if "action_taken" in obj:
        action = obj["action_taken"]
        title = obj.get("current_title", "")
        error = obj.get("error", "")

        # Skip "no action" responses — the navigator is saying "wrong agent"
        if "no navigation" in action.lower() or "requires the" in action.lower():
            return None

        if obj.get("success"):
            # Produce warm, conversational narration
            if title and title != "Google":
                return f'Done! {action}. The page now shows "{title}".'
            return f"Done! {action}."
        else:
            if error:
                return f"Hmm, I tried to {action.lower()}, but ran into an issue: {error}"
            return f"I tried to {action.lower()}, but it didn't work. Let me try another way."

    # VisionOutput: page_type, summary, interactive_elements, primary_action
    if "page_type" in obj and "summary" in obj and "interactive_elements" in obj:
        summary = obj["summary"]
        primary = obj.get("primary_action", "")
        banner = obj.get("has_cookie_banner", False)
        modal = obj.get("has_modal", False)
        parts = []
        if banner:
            parts.append("I notice there's a cookie consent banner on this page. I'll try to dismiss it.")
        if modal:
            parts.append("There's a popup dialog covering some content.")
        parts.append(summary)
        if primary:
            parts.append(f"You might want to: {primary}")
        return " ".join(parts)

    # SummaryOutput: page_type, title, summary, key_items
    if "page_type" in obj and "summary" in obj and "key_items" in obj:
        title = obj.get("title", "")
        summary = obj["summary"]
        items = obj.get("key_items", [])
        more = obj.get("has_more_content", False)
        parts = []
        if title:
            parts.append(f'"{title}"')
        parts.append(summary)
        if items:
            parts.append("\nHere's what I found:")
            for i, item in enumerate(items[:10], 1):
                parts.append(f"  {i}. {item}")
        if more:
            parts.append("\nThere's more content below -- I can scroll down if you'd like.")
        return "\n".join(parts)

    return None


# ================================================================
# WebSocket: Bidi-Streaming Voice Endpoint (canonical ADK pattern)
# ================================================================

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    """
    ADK Bidi-streaming endpoint following the canonical bidi-demo pattern.

    Uses the native-audio Live API model via ``streaming_runner`` so the
    agent speaks directly with natural voice.  Audio is sent/received as
    raw PCM binary frames; text transcriptions ride alongside as JSON.

    Protocol  (client → server):
      - Binary frame: raw PCM audio (16-bit LE, 16 kHz, mono)
      - Text frame:   JSON ``{"type": "text", "content": "..."}``
                      **or** plain-text string (auto-detected)

    Protocol  (server → client):
      - Binary frame: PCM audio response from Live API (24 kHz)
      - Text frame:   JSON event (transcript, tool activity, screenshot, …)
    """
    await websocket.accept()

    # ============================================================
    # Phase 2: Session Initialization (per WebSocket connection)
    # ============================================================

    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        speech_config=build_speech_config(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        session_resumption=types.SessionResumptionConfig(),
    )

    # Get or create ADK session
    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

    # One LiveRequestQueue per session — never reuse
    live_request_queue = LiveRequestQueue()

    logger.info(
        "ws_bidi_session_started",
        user_id=user_id,
        session_id=session_id,
    )

    # ============================================================
    # Phase 3: Bidi-streaming with run_live() event loop
    # ============================================================

    async def upstream_task():
        """Receive messages from WebSocket client → forward to LiveRequestQueue."""
        try:
            while True:
                data = await websocket.receive()

                if "bytes" in data:
                    # Binary frame: raw PCM audio from microphone
                    audio_blob = types.Blob(
                        mime_type="audio/pcm;rate=16000",
                        data=data["bytes"],
                    )
                    live_request_queue.send_realtime(audio_blob)

                elif "text" in data:
                    raw = data["text"]
                    try:
                        msg = json.loads(raw)
                    except (json.JSONDecodeError, ValueError):
                        msg = None

                    if isinstance(msg, dict):
                        if msg.get("type") == "text":
                            content = types.Content(
                                parts=[types.Part(text=msg["content"])]
                            )
                            live_request_queue.send_content(content)
                        elif msg.get("type") == "activity_start":
                            live_request_queue.send_activity_start()
                        elif msg.get("type") == "activity_end":
                            live_request_queue.send_activity_end()
                        elif msg.get("type") in ("settings", "ping"):
                            pass  # Ignore control messages
                    else:
                        # Plain text string (fallback / typed input)
                        if raw.strip():
                            content = types.Content(
                                parts=[types.Part(text=raw)]
                            )
                            live_request_queue.send_content(content)

        except WebSocketDisconnect:
            pass  # Client disconnected — handled in finally

    async def downstream_task():
        """Receive ADK events from run_live() → forward audio + text to client."""
        try:
            logger.info("downstream_starting_run_live")
            async for event in streaming_runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                logger.info(
                    "downstream_event",
                    has_content=bool(event.content),
                    author=getattr(event, "author", None),
                )
                # ── Extract audio and text from event parts ──
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        # Audio data → binary WebSocket frame
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            mime = getattr(inline, "mime_type", "") or ""
                            if "audio" in mime:
                                await websocket.send_bytes(inline.data)

                        # Text (transcription or model response) → JSON frame
                        text = getattr(part, "text", None)
                        if text:
                            author = getattr(event, "author", "noor") or "noor"
                            await websocket.send_text(json.dumps({
                                "type": "response",
                                "text": text,
                                "agent": author,
                            }))

                # ── Drain UI events (tool_start, tool_end, screenshot) ──
                await _drain_ui_events(websocket, user_id, session_id)

            logger.info("downstream_run_live_finished")
        except WebSocketDisconnect:
            logger.info("downstream_ws_disconnect")
        except Exception as e:
            logger.error("downstream_error", error=str(e), error_type=type(e).__name__)
            raise

    # Run both tasks concurrently
    try:
        results = await asyncio.gather(
            upstream_task(),
            downstream_task(),
            return_exceptions=True,
        )
        # Log any exceptions that were swallowed by gather
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task_name = "upstream" if i == 0 else "downstream"
                logger.error(
                    "gather_task_exception",
                    task=task_name,
                    error=str(result),
                    error_type=type(result).__name__,
                )
    finally:
        # ============================================================
        # Phase 4: Terminate Live API session
        # ============================================================
        live_request_queue.close()
        logger.info(
            "ws_bidi_session_ended",
            user_id=user_id,
            session_id=session_id,
        )


# ================================================================
# Text-Only Fallback Endpoint (non-streaming, for testing)
# ================================================================

@app.websocket("/ws/text/{user_id}/{session_id}")
async def text_endpoint(websocket: WebSocket, user_id: str, session_id: str):
    """Non-streaming text endpoint for testing without voice."""
    await websocket.accept()

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id,
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id,
        )

    logger.info(
        "ws_text_session_started",
        user_id=user_id,
        session_id=session_id,
    )

    try:
        while True:
            data = await websocket.receive()

            # Skip binary frames (audio from mic — not supported on text endpoint)
            if "bytes" in data:
                continue

            message = data.get("text", "")
            if not message:
                continue

            # Skip non-user messages (settings sync, heartbeats)
            try:
                parsed = json.loads(message)
                if isinstance(parsed, dict) and parsed.get("type") in ("settings", "ping"):
                    continue
            except (json.JSONDecodeError, ValueError):
                pass  # Plain text message — proceed

            content = types.Content(
                role="user",
                parts=[types.Part(text=message)],
            )

            last_invocation_id = None

            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=content,
            ):
                if hasattr(event, "invocation_id") and event.invocation_id:
                    last_invocation_id = event.invocation_id
                if event.content and event.content.parts:
                    author = getattr(event, "author", "")
                    for part in event.content.parts:
                        text = getattr(part, "text", None)
                        if not text:
                            continue
                        # Skip thinking/reasoning prefixes (e.g. **Thinking**)
                        stripped = text.strip()
                        if stripped.startswith("**") and stripped.count("**") == 2:
                            continue
                        # Convert structured sub-agent JSON to narration
                        if stripped.startswith("{") and stripped.endswith("}"):
                            try:
                                obj = json.loads(stripped)
                                if isinstance(obj, dict):
                                    narration = _narrate_structured(obj)
                                    if narration:
                                        await websocket.send_text(json.dumps({
                                            "type": "response",
                                            "text": narration,
                                            "agent": "noor",
                                        }))
                                        continue
                            except (json.JSONDecodeError, ValueError):
                                pass
                        # Non-JSON text → send directly
                        await websocket.send_text(json.dumps({
                            "type": "response",
                            "text": text,
                            "agent": author or "noor",
                        }))

                # Drain UI events from session state (tool_start, tool_end, screenshot)
                await _drain_ui_events(websocket, user_id, session_id)

            # Final drain — catches events pushed by the last tool callback
            await _drain_ui_events(websocket, user_id, session_id)

            # Session rewind on error pages
            session = await session_service.get_session(
                app_name=APP_NAME, user_id=user_id, session_id=session_id
            )
            if session and session.state.get("_should_rewind") and last_invocation_id:
                logger.info(
                    "session_rewind_triggered",
                    reason=session.state.get("_rewind_reason", "unknown"),
                    session_id=session_id,
                )
                try:
                    await runner.rewind_async(
                        user_id=user_id,
                        session_id=session_id,
                        rewind_before_invocation_id=last_invocation_id,
                    )
                    session.state["_should_rewind"] = False
                    session.state["_rewind_reason"] = ""
                except Exception as rewind_err:
                    logger.error(
                        "session_rewind_failed",
                        error=str(rewind_err),
                        session_id=session_id,
                    )

    except WebSocketDisconnect:
        logger.info("ws_text_session_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("ws_text_session_error", error=str(e), session_id=session_id)
        try:
            await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))
        except Exception:
            pass


# ================================================================
# Live Screen Stream (JPEG screenshots over WebSocket)
# ================================================================

SCREEN_FPS = 2          # Target frames per second
SCREEN_QUALITY = 50     # JPEG quality (1-100)
SCREEN_INTERVAL = 1.0 / SCREEN_FPS


@app.websocket("/ws-screen/{session_id}")
async def screen_stream(websocket: WebSocket, session_id: str):
    """Stream live JPEG screenshots of the browser at ~2 FPS.

    Each frame is sent as a binary WebSocket message (raw JPEG bytes).
    The client renders them in an <img> tag via Blob URL.

    Falls back gracefully: if the browser isn't started yet, waits
    and retries every second until it is, or until the client disconnects.
    """
    await websocket.accept()

    # Register subscriber
    if session_id not in _screen_subscribers:
        _screen_subscribers[session_id] = set()
    _screen_subscribers[session_id].add(websocket)

    logger.info("screen_stream_started", session_id=session_id)

    try:
        while True:
            service = get_browser_service()
            if service is None or not service.is_started:
                await asyncio.sleep(1.0)
                continue

            try:
                jpeg_bytes = await service.browser.take_screenshot(
                    full_page=False, quality=SCREEN_QUALITY,
                )
                if jpeg_bytes:
                    await websocket.send_bytes(jpeg_bytes)
            except WebSocketDisconnect:
                break
            except Exception as e:
                err_str = str(e).lower()
                if "close" in err_str or "disconnect" in err_str or "1000" in err_str:
                    break
                logger.debug("screen_stream_frame_error", error=str(e))

            await asyncio.sleep(SCREEN_INTERVAL)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("screen_stream_error", error=str(e))
    finally:
        _screen_subscribers.get(session_id, set()).discard(websocket)
        if session_id in _screen_subscribers and not _screen_subscribers[session_id]:
            del _screen_subscribers[session_id]
        logger.info("screen_stream_ended", session_id=session_id)
