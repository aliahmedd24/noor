/**
 * Screenshot — Live browser screenshot panel with annotation overlay.
 *
 * Shows the latest screenshot from Noor's browser session.
 * Annotations (bounding boxes around interactive elements) are drawn on a canvas overlay.
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
    this._visible = true;
    this._init();
  }

  _init() {
    this._el.classList.add("screenshot-panel");
    this._el.setAttribute("role", "complementary");
    this._el.setAttribute("aria-label", "Browser screenshot");

    // Header with toggle
    const header = document.createElement("div");
    header.className = "screenshot-panel__header";

    const title = document.createElement("span");
    title.className = "screenshot-panel__title";
    title.textContent = "Noor's View";
    header.appendChild(title);

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
