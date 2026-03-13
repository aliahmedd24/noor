// Noor — WebSocket client + audio capture/playback
// TODO: Implement in Phase 4 (Voice Interface)

"use strict";

const statusEl = document.getElementById("status");
const micBtn = document.getElementById("mic-btn");

micBtn.addEventListener("click", () => {
    statusEl.textContent = "Voice interface not yet connected.";
});
