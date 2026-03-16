/**
 * Toast — Lightweight notification system.
 *
 * Usage:
 *   import { toast } from "./components/toast.js";
 *   toast.info("Connected to Noor.");
 *   toast.error("Microphone access denied.", { action: "Retry", onClick: () => {} });
 */

const DURATION_MS = 5000;

class ToastManager {
  constructor() {
    this._container = null;
  }

  _ensureContainer() {
    if (this._container) return;
    this._container = document.createElement("div");
    this._container.className = "toast-container";
    this._container.setAttribute("role", "status");
    this._container.setAttribute("aria-live", "assertive");
    this._container.setAttribute("aria-atomic", "true");
    document.body.appendChild(this._container);
  }

  /**
   * Show a toast notification.
   * @param {string} message
   * @param {"info"|"error"|"success"} level
   * @param {{ action?: string, onClick?: () => void, duration?: number }} opts
   */
  show(message, level = "info", opts = {}) {
    this._ensureContainer();

    const el = document.createElement("div");
    el.className = `toast toast--${level}`;
    el.setAttribute("role", "alert");

    const msg = document.createElement("span");
    msg.className = "toast__message";
    msg.textContent = message;
    el.appendChild(msg);

    if (opts.action && opts.onClick) {
      const btn = document.createElement("button");
      btn.className = "toast__action";
      btn.textContent = opts.action;
      btn.addEventListener("click", () => {
        opts.onClick();
        this._dismiss(el);
      });
      el.appendChild(btn);
    }

    const close = document.createElement("button");
    close.className = "toast__close";
    close.setAttribute("aria-label", "Dismiss notification");
    close.textContent = "\u00d7";
    close.addEventListener("click", () => this._dismiss(el));
    el.appendChild(close);

    this._container.appendChild(el);

    // Auto-dismiss
    const duration = opts.duration ?? DURATION_MS;
    if (duration > 0) {
      setTimeout(() => this._dismiss(el), duration);
    }
  }

  info(message, opts) {
    this.show(message, "info", opts);
  }

  error(message, opts) {
    this.show(message, "error", opts);
  }

  success(message, opts) {
    this.show(message, "success", opts);
  }

  _dismiss(el) {
    if (!el.parentElement) return;
    el.classList.add("toast--exiting");
    el.addEventListener("animationend", () => el.remove(), { once: true });
    // Fallback if animation doesn't fire
    setTimeout(() => el.remove(), 400);
  }
}

export const toast = new ToastManager();
