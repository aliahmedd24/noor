/**
 * MicButton — Mic toggle with pulse animation and waveform canvas.
 *
 * States: idle | listening | disabled
 * Emits custom events: "mic:start", "mic:stop"
 */

export class MicButton {
  /**
   * @param {HTMLButtonElement} button
   * @param {HTMLCanvasElement} canvas  Waveform canvas element
   */
  constructor(button, canvas) {
    this._btn = button;
    this._canvas = canvas;
    this._ctx = canvas.getContext("2d");
    this._state = "idle"; // idle | listening | disabled
    this._analyser = null;
    this._animId = null;
    this._init();
  }

  _init() {
    this._btn.addEventListener("click", () => {
      if (this._state === "disabled") return;
      if (this._state === "listening") {
        this.stop();
      } else {
        this.start();
      }
    });

    // Size canvas to container
    this._resizeCanvas();
    window.addEventListener("resize", () => this._resizeCanvas());
  }

  _resizeCanvas() {
    const rect = this._canvas.parentElement.getBoundingClientRect();
    this._canvas.width = Math.min(rect.width, 320);
    this._canvas.height = 48;
  }

  /** Transition to listening state. */
  start() {
    this._state = "listening";
    this._btn.classList.add("mic-btn--active");
    this._btn.textContent = "Stop Listening";
    this._btn.setAttribute("aria-label", "Stop voice conversation");
    this._btn.setAttribute("aria-pressed", "true");
    this._btn.dispatchEvent(new CustomEvent("mic:start", { bubbles: true }));
  }

  /** Transition to idle state. */
  stop() {
    this._state = "idle";
    this._btn.classList.remove("mic-btn--active");
    this._btn.textContent = "Talk to Noor";
    this._btn.setAttribute("aria-label", "Start voice conversation");
    this._btn.setAttribute("aria-pressed", "false");
    this._stopWaveform();
    this._btn.dispatchEvent(new CustomEvent("mic:stop", { bubbles: true }));
  }

  /** Disable the button (e.g. not connected). */
  disable() {
    this._state = "disabled";
    this._btn.disabled = true;
    this._btn.classList.remove("mic-btn--active");
  }

  /** Enable the button. */
  enable() {
    this._btn.disabled = false;
    if (this._state === "disabled") this._state = "idle";
  }

  get isListening() {
    return this._state === "listening";
  }

  /**
   * Connect an AnalyserNode for waveform visualization.
   * @param {AnalyserNode} analyser
   */
  connectAnalyser(analyser) {
    this._analyser = analyser;
    this._drawWaveform();
  }

  _drawWaveform() {
    if (!this._analyser || this._state !== "listening") {
      this._clearCanvas();
      return;
    }

    const bufLen = this._analyser.fftSize;
    const data = new Uint8Array(bufLen);
    this._analyser.getByteTimeDomainData(data);

    const w = this._canvas.width;
    const h = this._canvas.height;
    const ctx = this._ctx;

    ctx.clearRect(0, 0, w, h);
    ctx.lineWidth = 2;
    ctx.strokeStyle = getComputedStyle(document.documentElement)
      .getPropertyValue("--accent")
      .trim() || "#4fc3f7";
    ctx.beginPath();

    const sliceW = w / bufLen;
    let x = 0;
    for (let i = 0; i < bufLen; i++) {
      const v = data[i] / 128.0;
      const y = (v * h) / 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      x += sliceW;
    }
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    this._animId = requestAnimationFrame(() => this._drawWaveform());
  }

  _stopWaveform() {
    if (this._animId) {
      cancelAnimationFrame(this._animId);
      this._animId = null;
    }
    this._analyser = null;
    this._clearCanvas();
  }

  _clearCanvas() {
    this._ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);
  }
}
