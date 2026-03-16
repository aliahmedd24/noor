/**
 * Noor — Main application entry point.
 *
 * Wires up WebSocket connection, audio capture/playback,
 * and all UI components (transcript, mic, screenshot, toast, onboarding, settings).
 *
 * Follows the ADK bidi-demo convention: /ws/{user_id}/{session_id}
 */

import { Transcript } from "./components/transcript.js";
import { MicButton } from "./components/mic-button.js";
import { ScreenshotPanel } from "./components/screenshot.js";
import { toast } from "./components/toast.js";
import { Onboarding } from "./components/onboarding.js";
import { Settings } from "./components/settings.js";

// ================================================================
// DOM References
// ================================================================

const statusBar = document.getElementById("status");
const statusDot = statusBar.querySelector(".status-bar__dot");
const statusText = statusBar.querySelector(".status-bar__text");
const micBtnEl = document.getElementById("mic-btn");
const waveformEl = document.getElementById("waveform");
const textForm = document.getElementById("text-form");
const textInput = document.getElementById("text-input");
const transcriptEl = document.getElementById("transcript");
const screenshotEl = document.getElementById("screenshot-panel");
const settingsBtn = document.getElementById("settings-btn");

// ================================================================
// Component Init
// ================================================================

const transcript = new Transcript(transcriptEl);
const micButton = new MicButton(micBtnEl, waveformEl);
const screenshotPanel = new ScreenshotPanel(screenshotEl);

const settings = new Settings(settingsBtn, (s) => {
  // Sync settings to server on change
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "settings", ...s }));
  }
});

// Onboarding
const onboarding = new Onboarding(
  () => textInput.focus(),
  (prompt) => sendText(prompt),
);
onboarding.showIfFirstVisit();

// ================================================================
// State
// ================================================================

let ws = null;
let audioContext = null;
let mediaStream = null;
let scriptProcessor = null;
let analyserNode = null;
let isConnected = false;
let reconnectDelay = 1000; // Exponential backoff start
let thinkingTimer = null;  // "Still thinking" reminder

// Audio playback — single AudioContext reused across chunks for gapless output
const audioQueue = [];
let isPlaying = false;
let playbackCtx = null;   // Reused 24 kHz AudioContext
let nextStartTime = 0;    // Scheduled start time for gapless chaining

// ================================================================
// Status Helpers
// ================================================================

function setStatus(text, state = "default") {
  statusText.textContent = text;
  statusBar.className = "status-bar";
  if (state === "connected") statusBar.classList.add("status-bar--connected");
  if (state === "error") statusBar.classList.add("status-bar--error");
}

// ================================================================
// WebSocket Connection (with exponential backoff)
// ================================================================

let currentUserId = null;
let currentSessionId = null;

function connectWebSocket() {
  currentUserId = "user-" + Math.random().toString(36).substr(2, 8);
  currentSessionId = "session-" + Date.now();
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  // Bidi endpoint handles both voice (binary PCM) and text (JSON).
  // The server uses the native-audio Live API model so responses are
  // always spoken aloud — ideal for accessibility.
  ws = new WebSocket(`${protocol}//${location.host}/ws/${currentUserId}/${currentSessionId}`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    isConnected = true;
    reconnectDelay = 1000; // Reset backoff
    micButton.enable();
    setStatus("Connected. Press the button or type to start.", "connected");
    toast.success("Connected to Noor.");

    // Send current settings
    ws.send(JSON.stringify({ type: "settings", ...settings.current }));

    // Start live screen stream
    screenshotPanel.connectStream(currentSessionId);
  };

  ws.onmessage = (event) => {
    clearThinkingTimer();
    if (event.data instanceof ArrayBuffer) {
      enqueueAudio(event.data);
    } else {
      try {
        const data = JSON.parse(event.data);
        handleEvent(data);
      } catch {
        transcript.addMessage("noor", event.data);
      }
    }
  };

  ws.onclose = () => {
    isConnected = false;
    micButton.disable();
    stopMicrophone();
    screenshotPanel.disconnectStream();
    setStatus("Disconnected. Reconnecting...", "error");

    // Exponential backoff: 1s, 2s, 4s, 8s, ... max 30s
    setTimeout(connectWebSocket, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 30000);
  };

  ws.onerror = () => {
    setStatus("Connection error.", "error");
  };
}

// ================================================================
// Event Handling
// ================================================================

function handleEvent(event) {
  // Any event from the server means Noor is responding — clear the timer
  clearThinkingTimer();

  // Screenshot events
  if (event.type === "screenshot") {
    screenshotPanel.update(event.data, event.annotations || []);
    return;
  }

  // Tool lifecycle events
  if (event.type === "tool_start") {
    const msg = `Noor is running: ${event.tool}...`;
    transcript.addToolActivity(event.tool, msg);
    setStatus(msg, "connected");
    return;
  }

  if (event.type === "tool_end") {
    transcript.removeToolActivity(event.tool);
    setStatus("Connected.", "connected");
    return;
  }

  // Error events
  if (event.type === "error") {
    toast.error(event.message || event.error || "Something went wrong.");
    return;
  }

  // Status events
  if (event.type === "status") {
    setStatus(event.message, "connected");
    return;
  }

  // Text endpoint response format: {"type": "response", "text": "...", "agent": "..."}
  if (event.type === "response" && event.text) {
    transcript.addMessage("noor", event.text);
    setStatus("Connected.", "connected");
    return;
  }

  // ADK content events (bidi streaming format)
  if (event.content && event.content.parts) {
    for (const part of event.content.parts) {
      if (part.text) {
        const speaker = event.author === "user" ? "user" : "noor";
        transcript.addMessage(speaker, part.text);
      }
    }
  }

  // Tool call events from ADK (legacy format)
  if (event.actions && event.actions.tool_calls) {
    for (const call of event.actions.tool_calls) {
      const name = call.name || "processing";
      transcript.addToolActivity(name, `Working: ${name}...`);
    }
  }
}

// ================================================================
// Microphone Capture
// ================================================================

async function startMicrophone() {
  // Barge-in: stop any playing audio when the user starts speaking
  stopPlayback();

  try {
    audioContext = new AudioContext({ sampleRate: 16000 });
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    const source = audioContext.createMediaStreamSource(mediaStream);

    // Analyser for waveform
    analyserNode = audioContext.createAnalyser();
    analyserNode.fftSize = 2048;
    source.connect(analyserNode);
    micButton.connectAnalyser(analyserNode);

    // ScriptProcessor for PCM capture
    scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
    scriptProcessor.onaudioprocess = (e) => {
      if (!micButton.isListening || !ws || ws.readyState !== WebSocket.OPEN) return;

      const float32 = e.inputBuffer.getChannelData(0);
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      ws.send(int16.buffer);
    };

    source.connect(scriptProcessor);
    scriptProcessor.connect(audioContext.destination);

    setStatus("Listening... Speak now.", "connected");
    transcript.addMessage("system", "Microphone active. Speak naturally.");
  } catch (err) {
    micButton.stop();
    setStatus("Microphone denied. Use text input.", "error");
    toast.error("Microphone access denied.", {
      action: "Retry",
      onClick: () => {
        micButton.start();
        startMicrophone();
      },
    });
  }
}

function stopMicrophone() {
  if (scriptProcessor) {
    scriptProcessor.disconnect();
    scriptProcessor = null;
  }
  if (analyserNode) {
    analyserNode.disconnect();
    analyserNode = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
  if (audioContext && audioContext.state !== "closed") {
    audioContext.close();
    audioContext = null;
  }
}

// ================================================================
// Audio Playback (24kHz PCM from server)
// ================================================================

function enqueueAudio(arrayBuffer) {
  audioQueue.push(arrayBuffer);
  if (!isPlaying) drainAudioQueue();
}

function drainAudioQueue() {
  if (audioQueue.length === 0) {
    isPlaying = false;
    return;
  }
  isPlaying = true;

  // Lazily create (or resume) a single 24 kHz AudioContext
  if (!playbackCtx || playbackCtx.state === "closed") {
    playbackCtx = new AudioContext({ sampleRate: 24000 });
    nextStartTime = 0;
  }
  if (playbackCtx.state === "suspended") {
    playbackCtx.resume();
  }

  // Schedule all queued chunks back-to-back for gapless playback
  let lastSource = null;
  while (audioQueue.length > 0) {
    const buffer = audioQueue.shift();
    try {
      const int16 = new Int16Array(buffer);
      const float32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768;
      }

      const audioBuffer = playbackCtx.createBuffer(1, float32.length, 24000);
      audioBuffer.getChannelData(0).set(float32);

      const src = playbackCtx.createBufferSource();
      src.buffer = audioBuffer;
      src.connect(playbackCtx.destination);

      // Schedule at the end of the previous chunk (or now if first)
      const startAt = Math.max(nextStartTime, playbackCtx.currentTime);
      src.start(startAt);
      nextStartTime = startAt + audioBuffer.duration;
      lastSource = src;
    } catch {
      // Skip bad chunks
    }
  }

  // When the last scheduled chunk finishes, check for more
  if (lastSource) {
    lastSource.onended = () => drainAudioQueue();
  } else {
    isPlaying = false;
  }
}

function stopPlayback() {
  audioQueue.length = 0;
  isPlaying = false;
  nextStartTime = 0;
  if (playbackCtx && playbackCtx.state !== "closed") {
    playbackCtx.close().catch(() => {});
    playbackCtx = null;
  }
}

// ================================================================
// Text Input
// ================================================================

const THINKING_MESSAGES = [
  "Just a moment, I'm working on that...",
  "Still on it — give me a sec...",
  "Hang tight, I'm figuring this out...",
  "Working on it, one moment please...",
  "Bear with me, almost there...",
];

function startThinkingTimer() {
  clearThinkingTimer();
  thinkingTimer = setTimeout(() => {
    const msg = THINKING_MESSAGES[Math.floor(Math.random() * THINKING_MESSAGES.length)];
    transcript.addMessage("noor", msg);
    setStatus(msg, "connected");
  }, 15000);
}

function clearThinkingTimer() {
  if (thinkingTimer) {
    clearTimeout(thinkingTimer);
    thinkingTimer = null;
  }
}

function sendText(text) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    toast.error("Not connected. Please wait...");
    return;
  }
  // Bidi endpoint accepts JSON {"type": "text", "content": "..."}
  ws.send(JSON.stringify({ type: "text", content: text }));
  transcript.addMessage("user", text);
  startThinkingTimer();
}

// ================================================================
// Event Listeners
// ================================================================

// Mic button events (from MicButton component)
micBtnEl.addEventListener("mic:start", () => {
  if (!isConnected) {
    micButton.stop();
    toast.error("Not connected yet. Please wait...");
    return;
  }
  startMicrophone();
});

micBtnEl.addEventListener("mic:stop", () => {
  stopMicrophone();
  setStatus("Microphone stopped.", "connected");
});

// Text form submit
textForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = textInput.value.trim();
  if (text) {
    sendText(text);
    textInput.value = "";
  }
});

// Keyboard shortcut: Space to toggle mic (when no input focused)
document.addEventListener("keydown", (e) => {
  const tag = document.activeElement.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON") return;

  if (e.code === "Space") {
    e.preventDefault();
    micBtnEl.click();
  }
});

// Offline detection
window.addEventListener("offline", () => {
  setStatus("You're offline. Noor will reconnect when you're back.", "error");
  toast.error("Network offline.", { duration: 0 });
});

window.addEventListener("online", () => {
  toast.info("Back online. Reconnecting...");
  if (!isConnected) connectWebSocket();
});

// ================================================================
// Boot
// ================================================================

micButton.disable();
connectWebSocket();
