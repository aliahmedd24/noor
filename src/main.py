"""Noor FastAPI entrypoint — WebSocket server, REST health checks, ADK runner."""

from __future__ import annotations

import sys

if sys.platform == "win32" and sys.version_info < (3, 14):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import json
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.config import settings
from src.utils.logging import setup_logging

setup_logging()
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# ADK runner + session service (created once, shared across connections)
# ---------------------------------------------------------------------------

session_service = InMemorySessionService()
_runner: Runner | None = None


def _get_runner() -> Runner:
    """Lazy-load the ADK runner to avoid import-time side effects."""
    global _runner
    if _runner is None:
        from src.agents import root_agent

        _runner = Runner(
            agent=root_agent,
            app_name="noor",
            session_service=session_service,
        )
    return _runner


# ---------------------------------------------------------------------------
# Browser lifecycle
# ---------------------------------------------------------------------------

_browser_manager = None


async def _start_browser() -> None:
    """Start the shared BrowserManager and inject into tool modules."""
    global _browser_manager

    from src.browser.manager import BrowserManager
    from src.vision.analyzer import ScreenAnalyzer
    from src.tools import browser_tools, vision_tools, page_tools

    _browser_manager = BrowserManager(
        headless=settings.noor_browser_headless,
        channel=settings.noor_browser_channel or None,
        cdp_endpoint=settings.noor_cdp_endpoint or None,
    )
    await _browser_manager.start()

    analyzer = ScreenAnalyzer()

    browser_tools.set_browser_manager(_browser_manager)
    vision_tools.set_browser_manager(_browser_manager)
    vision_tools.set_screen_analyzer(analyzer)
    page_tools.set_browser_manager(_browser_manager)

    # Mark the callback module as initialized so it skips re-init
    from src.agents import callbacks
    callbacks._initialized = True

    logger.info(
        "browser_started",
        strategy=_browser_manager.launch_strategy,
    )


async def _stop_browser() -> None:
    """Shut down the shared BrowserManager."""
    global _browser_manager
    if _browser_manager is not None:
        await _browser_manager.stop()
        _browser_manager = None
        logger.info("browser_stopped")


# ---------------------------------------------------------------------------
# FastAPI app with lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start browser on startup, stop on shutdown."""
    await _start_browser()
    yield
    await _stop_browser()


app = FastAPI(
    title="Noor",
    description="AI-powered web navigator for visually impaired users",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/client", StaticFiles(directory="client"), name="client")


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for Cloud Run."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "browser": _browser_manager is not None and _browser_manager.is_started,
    }


# ---------------------------------------------------------------------------
# WebSocket agent endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_agent(websocket: WebSocket):
    """WebSocket endpoint for real-time agent interaction.

    Protocol (JSON messages):
        Client -> Server: {"type": "message", "text": "Go to google.com"}
        Server -> Client: {"type": "agent_response", "text": "...", "done": true}
        Server -> Client: {"type": "error", "error": "..."}
    """
    await websocket.accept()

    runner = _get_runner()
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    session = await session_service.create_session(
        app_name="noor",
        user_id=user_id,
    )
    session_id = session.id

    logger.info("ws_session_started", user_id=user_id, session_id=session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Treat plain text as a message
                data = {"type": "message", "text": raw}

            msg_type = data.get("type", "message")
            text = data.get("text", "").strip()

            if msg_type != "message" or not text:
                await websocket.send_json(
                    {"type": "error", "error": "Send {\"type\":\"message\",\"text\":\"...\"}"}
                )
                continue

            logger.info("ws_user_message", text=text, session_id=session_id)

            # Build ADK content from user text
            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text)],
            )

            # Run agent and collect response
            response_parts: list[str] = []
            async for event in runner.run(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_parts.append(part.text)

            full_response = "\n".join(response_parts) if response_parts else ""

            await websocket.send_json({
                "type": "agent_response",
                "text": full_response,
                "done": True,
            })

            logger.info(
                "ws_agent_response",
                session_id=session_id,
                response_length=len(full_response),
            )

    except WebSocketDisconnect:
        logger.info("ws_session_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("ws_session_error", error=str(e), session_id=session_id)
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except Exception:
            pass
