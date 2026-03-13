# PHASE 4: VOICE INTERFACE — GEMINI LIVE API STREAMING

## Objective

Build the real-time voice interface that connects the user to Noor. This phase integrates ADK's Gemini Live API Toolkit for bidirectional audio streaming, enabling natural voice conversation with barge-in support. This is what makes Noor feel alive — the user speaks, Noor listens, processes, and speaks back in real-time.

This phase directly targets the **Innovation & Multimodal User Experience (40%)** criterion: "Does the agent 'See, Hear, and Speak' in a way that feels seamless?"

---

## 4.1 — STREAMING ARCHITECTURE

```
┌─────────────────┐          WebSocket          ┌──────────────────────┐
│  Browser Client  │ ◄═══════════════════════► │  FastAPI Server       │
│                  │   Audio PCM (16-bit,16kHz)  │                      │
│  - Mic capture   │   ────────────────────►    │  ┌─────────────────┐ │
│  - Speaker play  │                            │  │ LiveRequestQueue │ │
│  - Audio Worklet │   Audio PCM (24kHz)        │  │ (ADK Streaming)  │ │
│                  │   ◄────────────────────    │  └────────┬────────┘ │
└─────────────────┘                             │           │          │
                                                │           ▼          │
                                                │  ┌─────────────────┐ │
                                                │  │  ADK Runner      │ │
                                                │  │  + root_agent    │ │
                                                │  │  run_live()      │ │
                                                │  └────────┬────────┘ │
                                                │           │          │
                                                │           ▼          │
                                                │  ┌─────────────────┐ │
                                                │  │ Gemini Live API  │ │
                                                │  │ (Vertex AI)      │ │
                                                │  └─────────────────┘ │
                                                └──────────────────────┘
```

### Key Components

1. **Client (browser)**: Captures microphone audio via AudioWorklet, sends as PCM over WebSocket, receives and plays audio responses
2. **FastAPI Server**: Manages WebSocket connections, bridges to ADK's `LiveRequestQueue`
3. **ADK Streaming (`run_live`)**: Connects the agent to Gemini Live API for real-time audio processing with tool execution
4. **Gemini Live API**: Processes audio stream, generates spoken responses, handles Voice Activity Detection (VAD) and barge-in

---

## 4.2 — SERVER: FastAPI + ADK STREAMING (`src/main.py`)

```python
"""
Noor FastAPI Application — Main entry point.

Serves:
1. WebSocket endpoint for real-time voice streaming (ADK + Gemini Live API)
2. Static files for the client UI
3. Health check endpoint for Cloud Run

Architecture:
- Each WebSocket connection creates an ADK session with LiveRequestQueue
- Audio from the client is forwarded to the LiveRequestQueue
- Agent responses (audio) are streamed back to the client
- The root_agent handles all tool calls (browser, vision, etc.)
"""
# CRITICAL: Fix Windows asyncio event loop BEFORE any other imports.
# Playwright subprocess management fails with ProactorEventLoop on Windows.
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.streaming import LiveRequestQueue

from src.agents import root_agent
from src.browser.manager import BrowserManager
from src.tools.browser_tools import set_browser_manager
from src.tools.vision_tools import set_browser_manager as set_vision_browser
from src.config import settings


# === Lifespan: startup/shutdown ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""
    # Startup: launch browser
    browser = BrowserManager(headless=settings.browser_headless)
    await browser.start()
    set_browser_manager(browser)
    set_vision_browser(browser)
    app.state.browser = browser

    # Initialize ADK runner and session service
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="noor",
        session_service=session_service,
    )
    app.state.runner = runner
    app.state.session_service = session_service

    yield

    # Shutdown: close browser
    await browser.stop()


app = FastAPI(title="Noor", lifespan=lifespan)

# Serve client static files
app.mount("/static", StaticFiles(directory="client"), name="static")


# === Health Check (Cloud Run requirement) ===

@app.get("/health")
async def health():
    return {"status": "healthy", "agent": "noor"}


# === Client UI ===

@app.get("/")
async def index():
    return FileResponse("client/index.html")


# === WebSocket: Voice Streaming ===

@app.websocket("/ws/voice")
async def voice_stream(websocket: WebSocket):
    """
    WebSocket endpoint for bidirectional voice streaming.

    Protocol:
    - Client sends: binary frames (raw PCM audio, 16-bit, 16kHz, mono)
    - Client sends: text frames (JSON commands like {"type": "text", "content": "..."})
    - Server sends: binary frames (raw PCM audio, 24kHz, mono)
    - Server sends: text frames (JSON events like {"type": "transcript", "text": "..."})
    """
    await websocket.accept()

    # Create a unique session for this connection
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    session = await app.state.session_service.create_session(
        app_name="noor",
        user_id=user_id,
    )

    # Create the LiveRequestQueue for this session
    live_request_queue = LiveRequestQueue()

    # Task to forward client audio to ADK
    async def receive_audio():
        """Receive audio from client WebSocket and forward to LiveRequestQueue."""
        try:
            while True:
                data = await websocket.receive()

                if "bytes" in data:
                    # Binary frame: raw PCM audio from microphone
                    live_request_queue.send_realtime(data["bytes"])

                elif "text" in data:
                    import json
                    msg = json.loads(data["text"])

                    if msg.get("type") == "text":
                        # Text input (fallback for non-voice interaction)
                        live_request_queue.send_content(msg["content"])

                    elif msg.get("type") == "audio_end":
                        # Client signals end of speech
                        live_request_queue.send_realtime(b"", end_of_turn=True)

        except WebSocketDisconnect:
            live_request_queue.close()

    # Task to send agent responses back to client
    async def send_responses():
        """Process ADK agent events and send audio/text back to client."""
        try:
            async for event in app.state.runner.run_live(
                session=session,
                live_request_queue=live_request_queue,
            ):
                # Handle different event types from ADK
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            # Audio response — send as binary frame
                            await websocket.send_bytes(part.inline_data.data)

                        elif hasattr(part, "text") and part.text:
                            # Text response — send as JSON
                            import json
                            await websocket.send_text(json.dumps({
                                "type": "transcript",
                                "text": part.text,
                                "agent": event.author if hasattr(event, "author") else "noor",
                            }))

                # Handle transcription events
                if hasattr(event, "server_content"):
                    sc = event.server_content
                    if hasattr(sc, "input_transcription") and sc.input_transcription:
                        import json
                        await websocket.send_text(json.dumps({
                            "type": "user_transcript",
                            "text": sc.input_transcription.text,
                        }))
                    if hasattr(sc, "output_transcription") and sc.output_transcription:
                        import json
                        await websocket.send_text(json.dumps({
                            "type": "agent_transcript",
                            "text": sc.output_transcription.text,
                        }))

        except WebSocketDisconnect:
            pass

    # Run both tasks concurrently
    receive_task = asyncio.create_task(receive_audio())
    send_task = asyncio.create_task(send_responses())

    try:
        await asyncio.gather(receive_task, send_task)
    except Exception:
        receive_task.cancel()
        send_task.cancel()


# === Text-based fallback endpoint ===

@app.websocket("/ws/text")
async def text_stream(websocket: WebSocket):
    """
    WebSocket endpoint for text-only interaction (accessibility fallback).

    Protocol:
    - Client sends: text frames (user messages)
    - Server sends: text frames (JSON with agent responses)
    """
    await websocket.accept()
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    session = await app.state.session_service.create_session(
        app_name="noor", user_id=user_id,
    )

    try:
        while True:
            message = await websocket.receive_text()

            from google.genai import types
            content = types.Content(
                role="user",
                parts=[types.Part.from_text(message)]
            )

            async for event in app.state.runner.run_async(
                session_id=session.id,
                user_id=user_id,
                new_message=content,
            ):
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            import json
                            await websocket.send_text(json.dumps({
                                "type": "response",
                                "text": part.text,
                                "agent": event.author if hasattr(event, "author") else "noor",
                            }))

    except WebSocketDisconnect:
        pass
```

---

## 4.3 — NOOR VOICE PERSONA (`src/voice/persona.py`)

```python
"""
Noor voice persona configuration for Gemini Live API.

The Live API supports different voice presets. Noor uses a warm,
clear voice suitable for accessibility narration.
"""

# Available Gemini Live API voices:
# Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, Zephyr

NOOR_VOICE_CONFIG = {
    "voice": "Leda",              # Warm, clear female voice
    "language_code": "en-US",     # Primary language
    "response_modalities": ["AUDIO"],
    "input_audio_transcription": {},   # Enable input transcription
    "output_audio_transcription": {},  # Enable output transcription
    "system_instruction": (
        "You are Noor, a warm and patient AI assistant that helps "
        "visually impaired users navigate the web. Speak clearly and "
        "at a moderate pace. Describe visual elements in detail. "
        "Number items in lists. Be encouraging and supportive."
    ),
}

# Model ID for Live API streaming
# Check latest supported models at:
# https://google.github.io/adk-docs/get-started/streaming/quickstart-streaming/#supported-models
LIVE_MODEL_ID = "gemini-live-2.5-flash-native-audio"
```

### Integrating Voice Config with the Root Agent

The root agent's model should be set to the Live API model when running in streaming mode:

```python
# In src/agents/agent.py — when streaming mode is enabled
import os
from src.voice.persona import LIVE_MODEL_ID, NOOR_VOICE_CONFIG

if os.getenv("NOOR_STREAMING_MODE", "false").lower() == "true":
    orchestrator_agent.model = LIVE_MODEL_ID
    # Voice config is passed through ADK's run_live configuration
```

---

## 4.4 — CLIENT: ACCESSIBLE WEB UI (`client/`)

The client is intentionally minimal — Noor is a voice-first interface. The UI exists primarily for the demo video and as a fallback for text input.

### `client/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Noor — Your Eyes on the Web</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <!-- Skip to main content (accessibility) -->
    <a href="#main" class="skip-link">Skip to main content</a>

    <header role="banner">
        <h1>Noor <span aria-label="Light in Arabic">نور</span></h1>
        <p class="tagline">Your eyes on the web</p>
    </header>

    <main id="main" role="main">
        <!-- Status indicator -->
        <div id="status" role="status" aria-live="polite">
            Press the microphone button or type a command to begin.
        </div>

        <!-- Voice control -->
        <div class="voice-controls">
            <button id="mic-btn"
                    aria-label="Start speaking"
                    aria-pressed="false"
                    class="mic-button">
                🎤 Tap to Speak
            </button>
        </div>

        <!-- Conversation transcript (for demo video visibility) -->
        <div id="transcript"
             role="log"
             aria-label="Conversation transcript"
             aria-live="polite">
        </div>

        <!-- Text input fallback -->
        <div class="text-input">
            <label for="text-cmd" class="sr-only">Type a command</label>
            <input id="text-cmd"
                   type="text"
                   placeholder="Type a command (e.g., 'Go to BBC News')"
                   aria-label="Type a command">
            <button id="send-btn" aria-label="Send command">Send</button>
        </div>
    </main>

    <script src="/static/app.js"></script>
</body>
</html>
```

### `client/styles.css`

Design principles: **high contrast**, **large text**, **minimal visual clutter** — this is an accessibility-first UI.

```css
/* Accessibility-first styles for Noor */

:root {
    --bg: #1a1a2e;
    --bg-surface: #16213e;
    --text: #e8e8e8;
    --text-muted: #a0a0b0;
    --accent: #4fc3f7;
    --accent-active: #81d4fa;
    --error: #ef5350;
    --success: #66bb6a;
    --radius: 12px;
    --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem;
    font-size: 1.2rem;
    line-height: 1.6;
}

.skip-link {
    position: absolute;
    top: -100px;
    left: 0;
    background: var(--accent);
    color: #000;
    padding: 0.5rem 1rem;
    z-index: 100;
}
.skip-link:focus { top: 0; }

header { text-align: center; margin-bottom: 2rem; }
header h1 { font-size: 2.5rem; color: var(--accent); }
header .tagline { color: var(--text-muted); font-size: 1.1rem; }

#status {
    background: var(--bg-surface);
    padding: 1rem 2rem;
    border-radius: var(--radius);
    margin-bottom: 2rem;
    text-align: center;
    font-size: 1.3rem;
    min-height: 3rem;
    border: 2px solid var(--accent);
    max-width: 600px;
    width: 100%;
}

.mic-button {
    width: 200px;
    height: 200px;
    border-radius: 50%;
    border: 4px solid var(--accent);
    background: var(--bg-surface);
    color: var(--accent);
    font-size: 1.5rem;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 1rem auto;
}
.mic-button:hover, .mic-button:focus {
    background: var(--accent);
    color: var(--bg);
    transform: scale(1.05);
}
.mic-button[aria-pressed="true"] {
    background: var(--error);
    border-color: var(--error);
    color: white;
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239, 83, 80, 0.4); }
    50% { box-shadow: 0 0 0 20px rgba(239, 83, 80, 0); }
}

#transcript {
    max-width: 600px;
    width: 100%;
    max-height: 400px;
    overflow-y: auto;
    padding: 1rem;
    margin: 1rem 0;
}
#transcript .message {
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    border-radius: var(--radius);
    font-size: 1.1rem;
}
#transcript .user { background: #1e3a5f; text-align: right; }
#transcript .agent { background: var(--bg-surface); border-left: 3px solid var(--accent); }

.text-input {
    display: flex;
    gap: 0.5rem;
    max-width: 600px;
    width: 100%;
    margin-top: 1rem;
}
.text-input input {
    flex: 1;
    padding: 1rem;
    border-radius: var(--radius);
    border: 2px solid var(--text-muted);
    background: var(--bg-surface);
    color: var(--text);
    font-size: 1.1rem;
}
.text-input input:focus {
    border-color: var(--accent);
    outline: none;
}
.text-input button {
    padding: 1rem 2rem;
    border-radius: var(--radius);
    border: none;
    background: var(--accent);
    color: var(--bg);
    font-size: 1.1rem;
    cursor: pointer;
    font-weight: bold;
}

.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0,0,0,0);
}
```

### `client/app.js`

```javascript
/**
 * Noor Client — WebSocket voice/text client.
 *
 * Handles:
 * - Microphone capture via AudioWorklet (PCM 16-bit, 16kHz)
 * - WebSocket connection for audio and text streaming
 * - Audio playback of agent responses
 * - Transcript display for demo visibility
 */

const statusEl = document.getElementById("status");
const micBtn = document.getElementById("mic-btn");
const transcriptEl = document.getElementById("transcript");
const textInput = document.getElementById("text-cmd");
const sendBtn = document.getElementById("send-btn");

let ws = null;
let audioContext = null;
let mediaStream = null;
let isListening = false;

// === WebSocket Connection ===

function connectWebSocket() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${location.host}/ws/voice`);
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
        statusEl.textContent = "Connected. Tap the microphone to speak.";
    };

    ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
            // Audio response — play it
            playAudio(event.data);
        } else {
            // Text/JSON event
            const msg = JSON.parse(event.data);
            handleServerMessage(msg);
        }
    };

    ws.onclose = () => {
        statusEl.textContent = "Disconnected. Reconnecting...";
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
        statusEl.textContent = "Connection error.";
    };
}

function handleServerMessage(msg) {
    switch (msg.type) {
        case "transcript":
        case "agent_transcript":
            addTranscript("agent", msg.text);
            statusEl.textContent = "Noor: " + msg.text.slice(0, 100);
            break;
        case "user_transcript":
            addTranscript("user", msg.text);
            break;
        case "response":
            addTranscript("agent", msg.text);
            break;
    }
}

function addTranscript(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = role === "user" ? `You: ${text}` : `Noor: ${text}`;
    transcriptEl.appendChild(div);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

// === Microphone Capture ===

async function startMicrophone() {
    audioContext = new AudioContext({ sampleRate: 16000 });
    mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true }
    });

    const source = audioContext.createMediaStreamSource(mediaStream);

    // Use ScriptProcessor for simplicity (AudioWorklet is better for production)
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (e) => {
        if (!isListening || !ws || ws.readyState !== WebSocket.OPEN) return;

        const float32 = e.inputBuffer.getChannelData(0);
        const int16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
            int16[i] = Math.max(-32768, Math.min(32767, Math.floor(float32[i] * 32768)));
        }
        ws.send(int16.buffer);
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
}

function stopMicrophone() {
    if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop());
        mediaStream = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
}

// === Audio Playback ===

const playbackContext = new AudioContext({ sampleRate: 24000 });
const audioQueue = [];
let isPlaying = false;

function playAudio(arrayBuffer) {
    audioQueue.push(arrayBuffer);
    if (!isPlaying) processAudioQueue();
}

async function processAudioQueue() {
    isPlaying = true;
    while (audioQueue.length > 0) {
        const buffer = audioQueue.shift();
        const int16 = new Int16Array(buffer);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768;
        }

        const audioBuffer = playbackContext.createBuffer(1, float32.length, 24000);
        audioBuffer.getChannelData(0).set(float32);

        const source = playbackContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(playbackContext.destination);
        source.start();

        await new Promise(resolve => { source.onended = resolve; });
    }
    isPlaying = false;
}

// === Event Handlers ===

micBtn.addEventListener("click", async () => {
    if (!isListening) {
        await startMicrophone();
        isListening = true;
        micBtn.setAttribute("aria-pressed", "true");
        micBtn.textContent = "🔴 Listening...";
        statusEl.textContent = "Listening... Speak your command.";
    } else {
        isListening = false;
        stopMicrophone();
        micBtn.setAttribute("aria-pressed", "false");
        micBtn.textContent = "🎤 Tap to Speak";
        statusEl.textContent = "Microphone off. Tap to speak again.";
    }
});

sendBtn.addEventListener("click", () => {
    const text = textInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "text", content: text }));
    addTranscript("user", text);
    textInput.value = "";
});

textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendBtn.click();
});

// === Initialize ===
connectWebSocket();
```

---

## 4.5 — IMPLEMENTATION ORDER

1. **`src/voice/persona.py`** — Voice configuration
2. **`src/main.py`** — FastAPI server with WebSocket endpoints
3. **`client/index.html`** — Accessible UI shell
4. **`client/styles.css`** — High-contrast accessible styles
5. **`client/app.js`** — WebSocket client with mic/speaker
6. **`src/config.py`** — Settings from environment variables
7. **Test end-to-end** — Run locally with `uvicorn`, test voice and text

---

## 4.6 — `src/config.py`

```python
"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Noor application settings."""
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = False
    google_api_key: str = ""
    firestore_database: str = "(default)"
    noor_log_level: str = "INFO"
    noor_browser_headless: bool = True
    noor_browser_channel: str = ""   # "msedge" or "chrome" for Windows; empty for Docker/Cloud Run
    noor_cdp_endpoint: str = ""      # "http://localhost:9222" for CDP fallback; empty to skip
    noor_host: str = "0.0.0.0"
    noor_port: int = 8080
    noor_streaming_mode: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

---

## 4.7 — ACCEPTANCE CRITERIA

- [ ] FastAPI server starts with `uvicorn src.main:app`
- [ ] WebSocket connects at `/ws/voice` and `/ws/text`
- [ ] Microphone audio captured as PCM 16-bit 16kHz and sent over WebSocket
- [ ] Agent audio responses play back through browser speaker
- [ ] Transcriptions (user + agent) display in the transcript panel
- [ ] Text input fallback works via the text box
- [ ] Barge-in works: speaking while Noor is responding interrupts her
- [ ] Status indicator updates: connected, listening, processing, speaking
- [ ] UI is fully keyboard-navigable and screen-reader compatible
- [ ] Client handles reconnection on WebSocket disconnect

---

## 4.8 — NOTES ON STREAMING MODELS

The Gemini Live API requires specific model IDs. Check the latest at:
https://google.github.io/adk-docs/get-started/streaming/quickstart-streaming/#supported-models

As of the current ADK docs, models supporting Live API include:
- `gemini-live-2.5-flash-native-audio` (stable)
- `gemini-live-2.5-flash-preview-native-audio-09-2025` (deprecated March 19, 2026 — avoid)

**Important:** The streaming model is ONLY for the root agent in `run_live()` mode. Sub-agents that do vision analysis use the standard `gemini-2.5-flash` model via `generate_content` (non-streaming). ADK handles this seamlessly — the root agent streams with Live API while tool calls within sub-agents use standard API calls.
