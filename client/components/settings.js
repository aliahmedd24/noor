/**
 * Settings — Preferences panel with localStorage persistence.
 *
 * Controls: voice speed, text size, theme (dark/light).
 * Emits "settings:changed" custom event on the panel element.
 */

const STORAGE_KEY = "noor_settings";

const DEFAULTS = {
  voiceSpeed: "normal",   // slow | normal | fast
  textSize: "medium",     // small | medium | large
  theme: "dark",          // dark | light
};

export class Settings {
  /**
   * @param {HTMLElement} triggerBtn  Button that opens the panel
   * @param {(settings: object) => void} onChange  Callback when settings change
   */
  constructor(triggerBtn, onChange) {
    this._trigger = triggerBtn;
    this._onChange = onChange;
    this._panel = null;
    this._open = false;
    this._settings = this._load();
    this._init();
    this._apply();
  }

  _init() {
    this._trigger.addEventListener("click", () => this.toggle());

    // Build panel
    this._panel = document.createElement("div");
    this._panel.className = "settings-panel";
    this._panel.setAttribute("role", "dialog");
    this._panel.setAttribute("aria-label", "Settings");
    this._panel.hidden = true;

    this._panel.innerHTML = `
      <div class="settings-panel__header">
        <h3>Settings</h3>
        <button class="settings-panel__close" aria-label="Close settings">\u00d7</button>
      </div>
      <div class="settings-panel__body">
        <fieldset class="settings-panel__group">
          <legend>Voice Speed</legend>
          <label><input type="radio" name="voiceSpeed" value="slow"> Slow</label>
          <label><input type="radio" name="voiceSpeed" value="normal"> Normal</label>
          <label><input type="radio" name="voiceSpeed" value="fast"> Fast</label>
        </fieldset>
        <fieldset class="settings-panel__group">
          <legend>Text Size</legend>
          <label><input type="radio" name="textSize" value="small"> Small</label>
          <label><input type="radio" name="textSize" value="medium"> Medium</label>
          <label><input type="radio" name="textSize" value="large"> Large</label>
        </fieldset>
        <fieldset class="settings-panel__group">
          <legend>Theme</legend>
          <label><input type="radio" name="theme" value="dark"> Dark</label>
          <label><input type="radio" name="theme" value="light"> Light</label>
        </fieldset>
      </div>
    `;

    this._panel.querySelector(".settings-panel__close").addEventListener("click", () => this.close());

    // Listen for changes
    this._panel.addEventListener("change", (e) => {
      const input = e.target;
      if (input.name && input.value) {
        this._settings[input.name] = input.value;
        this._save();
        this._apply();
        this._onChange(this._settings);
      }
    });

    // Escape to close
    this._panel.addEventListener("keydown", (e) => {
      if (e.key === "Escape") this.close();
    });

    document.body.appendChild(this._panel);
    this._syncRadios();
  }

  _syncRadios() {
    for (const [key, val] of Object.entries(this._settings)) {
      const radio = this._panel.querySelector(`input[name="${key}"][value="${val}"]`);
      if (radio) radio.checked = true;
    }
  }

  _apply() {
    const root = document.documentElement;

    // Text size
    const sizes = { small: "1rem", medium: "1.25rem", large: "1.5rem" };
    root.style.setProperty("--base-font-size", sizes[this._settings.textSize] || sizes.medium);

    // Theme
    root.setAttribute("data-theme", this._settings.theme);
  }

  toggle() {
    if (this._open) this.close();
    else this.open();
  }

  open() {
    this._open = true;
    this._panel.hidden = false;
    this._panel.querySelector(".settings-panel__close").focus();
  }

  close() {
    this._open = false;
    this._panel.hidden = true;
    this._trigger.focus();
  }

  get current() {
    return { ...this._settings };
  }

  _load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
    } catch {
      return { ...DEFAULTS };
    }
  }

  _save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this._settings));
  }
}
