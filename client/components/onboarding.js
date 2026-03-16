/**
 * Onboarding — First-visit overlay with example prompts.
 *
 * Shows on first visit (localStorage flag). Dismissable.
 * Example prompt chips dispatch a custom "prompt:select" event.
 */

const STORAGE_KEY = "noor_onboarding_dismissed";

const EXAMPLE_PROMPTS = [
  "Go to google.com",
  "Search for flights from SFO to Tokyo",
  "Read me the top headlines on CNN",
  "Fill out the contact form",
  "What's on this page?",
];

export class Onboarding {
  /**
   * @param {() => void} onDismiss  Callback when overlay is dismissed
   * @param {(prompt: string) => void} onPromptSelect  Callback when example prompt is clicked
   */
  constructor(onDismiss, onPromptSelect) {
    this._onDismiss = onDismiss;
    this._onPromptSelect = onPromptSelect;
    this._overlay = null;
  }

  /** Show overlay if not previously dismissed. Returns true if shown. */
  showIfFirstVisit() {
    if (localStorage.getItem(STORAGE_KEY) === "true") return false;
    this._render();
    return true;
  }

  _render() {
    this._overlay = document.createElement("div");
    this._overlay.className = "onboarding";
    this._overlay.setAttribute("role", "dialog");
    this._overlay.setAttribute("aria-modal", "true");
    this._overlay.setAttribute("aria-label", "Welcome to Noor");

    this._overlay.innerHTML = `
      <div class="onboarding__card">
        <h2 class="onboarding__title">Welcome to Noor</h2>
        <p class="onboarding__subtitle">Your AI-powered eyes on the web</p>

        <div class="onboarding__steps">
          <div class="onboarding__step">
            <span class="onboarding__step-num">1</span>
            <span>Speak or type what you need</span>
          </div>
          <div class="onboarding__step">
            <span class="onboarding__step-num">2</span>
            <span>Noor sees the screen for you</span>
          </div>
          <div class="onboarding__step">
            <span class="onboarding__step-num">3</span>
            <span>Noor acts and narrates every step</span>
          </div>
        </div>

        <p class="onboarding__try">Try saying:</p>
        <div class="onboarding__chips" role="list" aria-label="Example prompts"></div>

        <button class="onboarding__cta" autofocus>Get Started</button>
      </div>
    `;

    // Populate chips
    const chipsContainer = this._overlay.querySelector(".onboarding__chips");
    for (const prompt of EXAMPLE_PROMPTS) {
      const chip = document.createElement("button");
      chip.className = "onboarding__chip";
      chip.setAttribute("role", "listitem");
      chip.textContent = prompt;
      chip.addEventListener("click", () => {
        this._dismiss();
        this._onPromptSelect(prompt);
      });
      chipsContainer.appendChild(chip);
    }

    // CTA button
    this._overlay.querySelector(".onboarding__cta").addEventListener("click", () => {
      this._dismiss();
    });

    // Escape key
    this._overlay.addEventListener("keydown", (e) => {
      if (e.key === "Escape") this._dismiss();
    });

    document.body.appendChild(this._overlay);

    // Trap focus
    this._overlay.querySelector(".onboarding__cta").focus();
  }

  _dismiss() {
    if (!this._overlay) return;
    localStorage.setItem(STORAGE_KEY, "true");
    this._overlay.classList.add("onboarding--exiting");
    this._overlay.addEventListener("animationend", () => {
      this._overlay.remove();
      this._overlay = null;
    }, { once: true });
    setTimeout(() => {
      if (this._overlay) {
        this._overlay.remove();
        this._overlay = null;
      }
    }, 400);
    this._onDismiss();
  }
}
