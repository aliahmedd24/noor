/**
 * Transcript — Chat-bubble styled conversation panel.
 *
 * Renders user messages right-aligned, Noor messages left-aligned,
 * system messages as inline notices, and tool activity as spinners.
 */

const SCROLL_THRESHOLD = 60; // px from bottom to auto-scroll

export class Transcript {
  /** @param {HTMLElement} container */
  constructor(container) {
    this._el = container;
    this._userScrolledUp = false;
    this._scrollBtn = null;
    this._init();
  }

  _init() {
    this._el.classList.add("transcript");
    this._el.setAttribute("role", "log");
    this._el.setAttribute("aria-label", "Conversation transcript");
    this._el.setAttribute("aria-live", "polite");

    // Scroll-to-bottom button
    this._scrollBtn = document.createElement("button");
    this._scrollBtn.className = "transcript__scroll-btn";
    this._scrollBtn.setAttribute("aria-label", "Scroll to latest message");
    this._scrollBtn.textContent = "\u2193";
    this._scrollBtn.hidden = true;
    this._scrollBtn.addEventListener("click", () => this.scrollToBottom());
    this._el.parentElement.appendChild(this._scrollBtn);

    this._el.addEventListener("scroll", () => {
      const gap = this._el.scrollHeight - this._el.scrollTop - this._el.clientHeight;
      this._userScrolledUp = gap > SCROLL_THRESHOLD;
      this._scrollBtn.hidden = !this._userScrolledUp;
    });
  }

  /**
   * Add a message bubble to the transcript.
   * @param {"user"|"noor"|"system"} speaker
   * @param {string} text
   */
  addMessage(speaker, text) {
    const bubble = document.createElement("div");
    bubble.className = `bubble bubble--${speaker}`;
    bubble.setAttribute("role", "listitem");

    if (speaker !== "system") {
      const label = document.createElement("span");
      label.className = "bubble__label";
      label.textContent = speaker === "user" ? "You" : "Noor";
      bubble.appendChild(label);
    }

    const body = document.createElement("span");
    body.className = "bubble__body";
    body.textContent = text;
    bubble.appendChild(body);

    const time = document.createElement("time");
    time.className = "bubble__time";
    time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    bubble.appendChild(time);

    this._el.appendChild(bubble);
    if (!this._userScrolledUp) this.scrollToBottom();
  }

  /**
   * Show a tool activity indicator.
   * @param {string} toolName
   * @param {string} message
   * @returns {HTMLElement} The indicator element (call remove() on tool_end).
   */
  addToolActivity(toolName, message) {
    const indicator = document.createElement("div");
    indicator.className = "bubble bubble--tool";
    indicator.setAttribute("role", "status");
    indicator.setAttribute("aria-live", "polite");
    indicator.innerHTML =
      `<span class="spinner" aria-hidden="true"></span>` +
      `<span class="bubble__body">${this._escapeHtml(message)}</span>`;
    indicator.dataset.tool = toolName;
    this._el.appendChild(indicator);
    if (!this._userScrolledUp) this.scrollToBottom();
    return indicator;
  }

  /** Remove a specific tool activity indicator. */
  removeToolActivity(toolName) {
    const el = this._el.querySelector(`.bubble--tool[data-tool="${toolName}"]`);
    if (el) el.remove();
  }

  scrollToBottom() {
    this._el.scrollTop = this._el.scrollHeight;
    this._userScrolledUp = false;
    if (this._scrollBtn) this._scrollBtn.hidden = true;
  }

  _escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }
}
