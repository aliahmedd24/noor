"""Noor FastAPI entrypoint — WebSocket server, REST health checks, ADK runner."""

from __future__ import annotations

import sys

if sys.platform == "win32" and sys.version_info < (3, 14):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncio
import json
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from google.adk.runners import InMemoryRunner
from google.adk.streaming import LiveRequestQueue
from google.genai import types

from src.config import settings
from src.utils.logging import setup_logging

setup_logging()
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# ADK runner (created once, shared across connections)
# ---------------------------------------------------------------------------

_runner: InMemoryRunner | None = None


def _get_runner() -> InMemoryRunner:
    """Lazy-load the ADK InMemoryRunner to avoid import-time side effects.

    Browser and vision dependencies are initialized lazily via the
    ``ensure_tools_initialized`` before_agent_callback on the orchestrator
    (see src/agents/callbacks.py). No separate browser startup step is
    needed here — the callback handles it on the first agent invocation.
    """
    global _runner
    if _runner is None:
        from src.agents.agent import root_agent
        from src.agents.plugins import get_plugins

        _runner = InMemoryRunner(
            agent=root_agent,
            app_name="noor",
            plugins=get_plugins(),
        )
    return _runner


# ---------------------------------------------------------------------------
# Browser shutdown helper
# ---------------------------------------------------------------------------


async def _stop_browser() -> None:
    """Shut down the browser if the callback initialized one."""
    from src.browser.service import get_browser_service

    service = get_browser_service()
    if service is not None and service.is_started:
        await service.stop()
        logger.info("browser_stopped")


# ---------------------------------------------------------------------------
# FastAPI app with lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Yield during app lifetime; clean up browser on shutdown."""
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
    from src.browser.service import get_browser_service

    service = get_browser_service()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "browser": service is not None and service.is_started,
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
    session = await runner.session_service.create_session(
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

            # Run agent and collect response, tracking invocation ID
            response_parts: list[str] = []
            last_invocation_id = None
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content,
            ):
                if hasattr(event, "invocation_id") and event.invocation_id:
                    last_invocation_id = event.invocation_id
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            response_parts.append(part.text)

            full_response = "\n".join(response_parts) if response_parts else ""

            # Phase 4: Check for rewind signal (error page recovery)
            session = await runner.session_service.get_session(
                app_name="noor", user_id=user_id, session_id=session_id
            )
            if session.state.get("_should_rewind") and last_invocation_id:
                logger.info(
                    "session_rewind_triggered",
                    reason=session.state.get("_rewind_reason", "unknown"),
                    invocation_id=last_invocation_id,
                    session_id=session_id,
                )
                try:
                    await runner.rewind_async(
                        user_id=user_id,
                        session_id=session_id,
                        rewind_before_invocation_id=last_invocation_id,
                    )
                    # Clear the rewind flag
                    session.state["_should_rewind"] = False
                    session.state["_rewind_reason"] = ""

                    # Send recovery message to agent
                    recovery_content = types.Content(
                        role="user",
                        parts=[types.Part.from_text(
                            "The last action led to an error page. "
                            "Please go back and try a different approach."
                        )],
                    )
                    recovery_parts: list[str] = []
                    async for event in runner.run_async(
                        user_id=user_id,
                        session_id=session_id,
                        new_message=recovery_content,
                    ):
                        if event.content and event.content.parts:
                            for part in event.content.parts:
                                if part.text:
                                    recovery_parts.append(part.text)

                    if recovery_parts:
                        full_response = "\n".join(recovery_parts)
                except Exception as rewind_err:
                    logger.error(
                        "session_rewind_failed",
                        error=str(rewind_err),
                        session_id=session_id,
                    )

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


# ---------------------------------------------------------------------------
# Live streaming WebSocket endpoint (Phase 5)
# ---------------------------------------------------------------------------


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket endpoint for real-time streaming agent interaction.

    Uses ADK LiveRequestQueue and runner.run_live() for low-latency
    bidirectional communication. Text streaming first; audio can be
    added later with gemini-live-2.5-flash-native-audio.

    Protocol (JSON messages):
        Client -> Server: {"type": "message", "text": "Go to google.com"}
        Server -> Client: {"type": "agent_response", "text": "...", "done": false}
        Server -> Client: {"type": "agent_response", "text": "", "done": true}
        Server -> Client: {"type": "telemetry", "text": "Looking at the page..."}
        Server -> Client: {"type": "error", "error": "..."}
    """
    await websocket.accept()

    runner = _get_runner()
    user_id = f"live-{uuid.uuid4().hex[:8]}"
    session = await runner.session_service.create_session(
        app_name="noor",
        user_id=user_id,
    )

    logger.info("ws_live_session_started", user_id=user_id, session_id=session.id)

    live_queue = LiveRequestQueue()

    async def ws_reader():
        """Read from WebSocket, push to LiveRequestQueue."""
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"type": "message", "text": raw}

                if data.get("type") == "message":
                    text = data.get("text", "").strip()
                    if text:
                        live_queue.send_content(types.Content(
                            role="user",
                            parts=[types.Part.from_text(text)],
                        ))
        except WebSocketDisconnect:
            live_queue.close()
        except Exception as e:
            logger.error("ws_live_reader_error", error=str(e))
            live_queue.close()

    async def live_reader():
        """Read from runner.run_live(), push to WebSocket."""
        try:
            async for event in runner.run_live(
                session=session,
                live_request_queue=live_queue,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            await websocket.send_json({
                                "type": "agent_response",
                                "text": part.text,
                                "done": False,
                            })
            await websocket.send_json({
                "type": "agent_response",
                "text": "",
                "done": True,
            })
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error("ws_live_writer_error", error=str(e))
            try:
                await websocket.send_json({"type": "error", "error": str(e)})
            except Exception:
                pass

    try:
        await asyncio.gather(ws_reader(), live_reader())
    except Exception as e:
        logger.error("ws_live_session_error", error=str(e))
    finally:
        logger.info("ws_live_session_ended", user_id=user_id, session_id=session.id)
