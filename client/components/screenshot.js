/**
 * Screenshot — Live browser screenshot panel with annotation overlay.
 *
 * Shows a real-time feed of Noor's browser session via a dedicated
 * WebSocket (/ws-screen/{session_id}) streaming JPEG frames at ~2 FPS.
 * Annotations (bounding boxes around interactive elements) are drawn
 * on a canvas overlay when provided via the update() method.
 */

export class ScreenshotPanel {
  /**
   * @param {HTMLElement} container  The panel container element
   */
  constructor(container) {
    this._el = container;
    this._img = null;
    this._canvas = null;
    this._toggleBtn = null;
    this._liveDot = null;
    this._visible = true;
    this._screenWs = null;
    this._lastBlobUrl = null;
    this._init();
  }

  _init() {
    this._el.classList.add("screenshot-panel");
    this._el.setAttribute("role", "complementary");
    this._el.setAttribute("aria-label", "Browser screenshot");

    // Header with live dot + toggle
    const header = document.createElement("div");
    header.className = "screenshot-panel__header";

    const titleWrap = document.createElement("span");
    titleWrap.className = "screenshot-panel__title";

    this._liveDot = document.createElement("span");
    this._liveDot.className = "screenshot-panel__live-dot";
    this._liveDot.setAttribute("aria-hidden", "true");
    this._liveDot.hidden = true;
    titleWrap.appendChild(this._liveDot);

    const titleText = document.createTextNode(" Noor\u2019s View");
    titleWrap.appendChild(titleText);
    header.appendChild(titleWrap);

    this._toggleBtn = document.createElement("button");
    this._toggleBtn.className = "screenshot-panel__toggle";
    this._toggleBtn.setAttribute("aria-label", "Hide screenshot panel");
    this._toggleBtn.textContent = "\u2212";
    this._toggleBtn.addEventListener("click", () => this.toggle());
    header.appendChild(this._toggleBtn);

    this._el.appendChild(header);

    // Image + canvas wrapper
    const wrapper = document.createElement("div");
    wrapper.className = "screenshot-panel__content";

    this._img = document.createElement("img");
    this._img.className = "screenshot-panel__img";
    this._img.alt = "Current browser screenshot";
    this._img.src = "";
    this._img.hidden = true;
    wrapper.appendChild(this._img);

    this._canvas = document.createElement("canvas");
    this._canvas.className = "screenshot-panel__overlay";
    this._canvas.setAttribute("aria-hidden", "true");
    wrapper.appendChild(this._canvas);

    const placeholder = document.createElement("p");
    placeholder.className = "screenshot-panel__placeholder";
    placeholder.textContent = "No screenshot yet. Ask Noor to navigate somewhere!";
    wrapper.appendChild(placeholder);

    this._placeholder = placeholder;
    this._el.appendChild(wrapper);

    // Mobile: default hidden
    if (window.innerWidth < 768) {
      this.hide();
    }
  }

  // ── Live Screen Stream ──────────────────────────────────────────

  /**
   * Connect to the live screen-stream WebSocket endpoint.
   * @param {string} sessionId  The session ID to subscribe to
   */
  connectStream(sessionId) {
    this.disconnectStream();

    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${location.host}/ws-screen/${sessionId}`;
    this._screenWs = new WebSocket(url);
    this._screenWs.binaryType = "blob";

    this._screenWs.onopen = () => {
      this._liveDot.hidden = false;
    };

    this._screenWs.onmessage = (event) => {
      if (event.data instanceof Blob) {
        this._updateFromBlob(event.data);
      }
    };

    this._screenWs.onclose = () => {
      this._liveDot.hidden = true;
    };

    this._screenWs.onerror = () => {
      this._liveDot.hidden = true;
    };
  }

  /**
   * Disconnect from the live screen-stream WebSocket.
   */
  disconnectStream() {
    if (this._screenWs) {
      this._screenWs.close();
      this._screenWs = null;
    }
    this._liveDot.hidden = true;
    if (this._lastBlobUrl) {
      URL.revokeObjectURL(this._lastBlobUrl);
      this._lastBlobUrl = null;
    }
  }

  /**
   * Update the screenshot image from a raw JPEG Blob (from the stream).
   * @param {Blob} blob  JPEG image blob
   */
  _updateFromBlob(blob) {
    // Revoke previous blob URL to avoid memory leaks
    if (this._lastBlobUrl) {
      URL.revokeObjectURL(this._lastBlobUrl);
    }
    this._lastBlobUrl = URL.createObjectURL(blob);
    this._img.src = this._lastBlobUrl;
    this._img.hidden = false;
    this._placeholder.hidden = true;
  }

  // ── Existing API (base64 + annotations) ─────────────────────────

  /**
   * Update the screenshot with new image data and optional annotations.
   * @param {string} base64Jpeg  Base64-encoded JPEG data
   * @param {Array<{x: number, y: number, width: number, height: number, label?: string}>} annotations
   */
  update(base64Jpeg, annotations = []) {
    this._img.src = `data:image/jpeg;base64,${base64Jpeg}`;
    this._img.hidden = false;
    this._placeholder.hidden = true;

    this._img.onload = () => {
      this._drawAnnotations(annotations);
    };
  }

  _drawAnnotations(annotations) {
    const w = this._img.naturalWidth;
    const h = this._img.naturalHeight;
    this._canvas.width = this._img.clientWidth;
    this._canvas.height = this._img.clientHeight;

    const ctx = this._canvas.getContext("2d");
    ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);

    if (!annotations.length) return;

    const scaleX = this._canvas.width / w;
    const scaleY = this._canvas.height / h;

    ctx.strokeStyle = "#4fc3f7";
    ctx.lineWidth = 2;
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillStyle = "#4fc3f7";

    for (const ann of annotations) {
      const x = ann.x * scaleX;
      const y = ann.y * scaleY;
      const bw = ann.width * scaleX;
      const bh = ann.height * scaleY;

      ctx.strokeRect(x, y, bw, bh);

      if (ann.label) {
        ctx.fillStyle = "rgba(0,0,0,0.7)";
        ctx.fillRect(x, y - 16, ctx.measureText(ann.label).width + 8, 16);
        ctx.fillStyle = "#4fc3f7";
        ctx.fillText(ann.label, x + 4, y - 4);
      }
    }
  }

  toggle() {
    if (this._visible) this.hide();
    else this.show();
  }

  show() {
    this._visible = true;
    this._el.classList.remove("screenshot-panel--hidden");
    this._toggleBtn.textContent = "\u2212";
    this._toggleBtn.setAttribute("aria-label", "Hide screenshot panel");
  }

  hide() {
    this._visible = false;
    this._el.classList.add("screenshot-panel--hidden");
    this._toggleBtn.textContent = "+";
    this._toggleBtn.setAttribute("aria-label", "Show screenshot panel");
  }
}
