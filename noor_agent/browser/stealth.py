"""Stealth evasion for Playwright — defeat common bot-detection systems.

Applies JavaScript patches and launch-arg tweaks that make the automated
browser indistinguishable from a regular user's browser session.  Covers
the detection vectors used by Cloudflare, DataDome, PerimeterX, Akamai
Bot Manager, and similar systems.

Usage:
    context = await browser.new_context(...)
    await apply_stealth(context)
"""

from __future__ import annotations

from playwright.async_api import BrowserContext

import structlog

logger = structlog.get_logger(__name__)

# ──────────────────────────────────────────────────────────────────
# Additional Chromium flags for stealth (merge into LAUNCH_ARGS)
# ──────────────────────────────────────────────────────────────────

STEALTH_LAUNCH_ARGS: list[str] = [
    # Hide the "Chrome is being controlled by automated test software" bar
    "--disable-blink-features=AutomationControlled",
    # Prevent WebRTC from leaking the real internal IP
    "--disable-features=WebRtcHideLocalIpsWithMdns",
    # Disable the automation extension that some detectors look for
    "--disable-component-extensions-with-background-pages",
    # Make headless mode less detectable
    "--disable-background-networking",
]

# ──────────────────────────────────────────────────────────────────
# JavaScript stealth patches (injected via addInitScript)
# ──────────────────────────────────────────────────────────────────

_STEALTH_JS = """\
// ── 1. navigator.webdriver ──────────────────────────────────────
// Playwright sets this to true.  Every bot detector checks it first.
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true,
});

// ── 2. window.chrome runtime ────────────────────────────────────
// Real Chrome exposes window.chrome with a runtime object.
// Headless/automation modes leave it missing or incomplete.
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.runtime) {
    window.chrome.runtime = {
        connect: function() {},
        sendMessage: function() {},
        id: undefined,
    };
}

// ── 3. navigator.plugins ────────────────────────────────────────
// Real browsers have 3–5 plugins.  Headless has 0.
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer',
              description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
              description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin',
              description: '' },
        ];
        plugins.length = 3;
        plugins.refresh = function() {};
        plugins.item = function(i) { return this[i] || null; };
        plugins.namedItem = function(n) {
            return this.find(p => p.name === n) || null;
        };
        return plugins;
    },
    configurable: true,
});

// ── 4. navigator.languages ──────────────────────────────────────
// Some detectors check that languages is a non-empty frozen array.
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
    configurable: true,
});

// ── 5. Permissions.query override ───────────────────────────────
// Headless Chrome returns 'denied' for notification permission
// which real Chrome returns 'prompt'.  Detectors use this delta.
const _origQuery = window.navigator.permissions.query.bind(
    window.navigator.permissions
);
window.navigator.permissions.query = (params) => {
    if (params.name === 'notifications') {
        return Promise.resolve({ state: Notification.permission });
    }
    return _origQuery(params);
};

// ── 6. WebGL vendor/renderer ────────────────────────────────────
// Headless often exposes "Google SwiftShader" which is a red flag.
// We don't override the actual WebGL calls (too fragile), but we
// ensure the debug info extension returns plausible strings.
(function() {
    const getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        // UNMASKED_VENDOR_WEBGL = 0x9245, UNMASKED_RENDERER_WEBGL = 0x9246
        if (param === 0x9245) return 'Google Inc. (Intel)';
        if (param === 0x9246) return 'ANGLE (Intel, Intel(R) UHD Graphics, OpenGL 4.1)';
        return getParam.call(this, param);
    };
})();

// ── 7. iframe contentWindow ─────────────────────────────────────
// Some detectors create a hidden iframe and check if its
// contentWindow.chrome matches the parent's window.chrome.
// This is already handled by patch #2 above since addInitScript
// runs in all frames.

// ── 8. console.debug detection ──────────────────────────────────
// Some fingerprinters check if console.debug is native code.
// Don't touch it — just make sure we didn't override it.
"""



# ──────────────────────────────────────────────────────────────────
# Auto-dismiss cookie banners and consent overlays
# ──────────────────────────────────────────────────────────────────

_COOKIE_DISMISS_JS = """\
(function() {
  // ── CSS: immediately hide known cookie-consent containers ─────
  const style = document.createElement('style');
  style.textContent = `
    /* OneTrust / Cookiebot / TrustArc / generic */
    #onetrust-banner-sdk,
    #onetrust-consent-sdk,
    .onetrust-pc-dark-filter,
    #CybotCookiebotDialog,
    #CybotCookiebotDialogBodyUnderlay,
    #cookiebanner,
    #cookie-banner,
    #cookie-consent,
    #cookie-notice,
    #cookie-law-info-bar,
    .cookie-banner,
    .cookie-consent,
    .cookie-notice,
    .cc-window,
    .cc-banner,
    .cc-overlay,
    .gdpr-banner,
    .consent-banner,
    .consent-modal,
    [id*="sp_message_container"],
    [class*="CookieConsent"],
    [class*="cookieConsent"],
    [class*="cookie-consent"],
    [class*="cookie-banner"],
    [aria-label*="cookie" i],
    [aria-label*="consent" i],
    div[class*="truste"],
    .fc-consent-root,
    #usercentrics-root,
    .qc-cmp2-container {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
      pointer-events: none !important;
      height: 0 !important;
      overflow: hidden !important;
    }
    /* Remove overlay backdrops that dim the page */
    .onetrust-pc-dark-filter,
    #CybotCookiebotDialogBodyUnderlay,
    .cc-overlay,
    [class*="consent-overlay"],
    [class*="cookie-overlay"] {
      display: none !important;
    }
    /* Restore scrolling blocked by consent managers */
    html.onetrust-pc-dark-filter,
    body.onetrust-pc-dark-filter,
    html.cookie-consent-active,
    body.cookie-consent-active {
      overflow: auto !important;
      position: static !important;
    }
  `;
  document.head.appendChild(style);

  // ── JS: click accept/dismiss buttons when they appear ─────────
  const ACCEPT_SELECTORS = [
    '#onetrust-accept-btn-handler',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    '.cc-accept-all',
    '.cc-btn.cc-dismiss',
    '[data-testid="cookie-policy-manage-dialog-btn-accept-all"]',
    'button[data-cookiefirst-action="accept"]',
    '.fc-cta-consent',
    'button.consent-accept',
    'button.cookie-accept',
    // SourcePoint (BBC, many news sites)
    'button[title="I agree"]',
    'button[title="Accept"]',
    'button[title="Accept all"]',
    '.sp_choice_type_11',          // SourcePoint "accept" button class
    '.sp_choice_type_ACCEPT_ALL',
  ];

  // Text patterns matched against button textContent.trim()
  const TEXT_PATTERNS = [
    /^accept all$/i,
    /^accept cookies$/i,
    /^accept$/i,
    /^i agree$/i,
    /^agree$/i,
    /^i do not agree$/i,
    /^got it$/i,
    /^ok$/i,
    /^allow all$/i,
    /^allow cookies$/i,
    /^reject all$/i,
    /^reject$/i,
    /^decline$/i,
    /^close$/i,
    /^no,? thanks$/i,
    /^continue without accepting$/i,
  ];

  // Inside a SourcePoint iframe, the whole document IS the consent dialog.
  // Detect this so we can search all buttons globally, not just in containers.
  const isConsentIframe = (
    window !== window.top &&
    (document.title === '' || /consent|privacy|cookie|gdpr|sp_message/i.test(
      document.title + ' ' + location.href + ' ' + document.body?.id
    ))
  );

  function tryDismiss() {
    // Strategy 1: known selectors
    for (const sel of ACCEPT_SELECTORS) {
      try {
        const btn = document.querySelector(sel);
        if (btn && btn.offsetParent !== null) {
          btn.click();
          return true;
        }
      } catch {}
    }

    // Strategy 2: text-match on visible buttons inside consent-like containers
    const containers = document.querySelectorAll(
      '[id*="cookie" i], [id*="consent" i], [class*="cookie" i], [class*="consent" i], ' +
      '[id*="gdpr" i], [class*="gdpr" i], [role="dialog"], [aria-modal="true"], ' +
      '[class*="message-component"], [id*="sp_message"], .cmp-container'
    );
    for (const container of containers) {
      const buttons = container.querySelectorAll('button, a[role="button"], [role="button"]');
      for (const btn of buttons) {
        const text = (btn.textContent || '').trim();
        if (TEXT_PATTERNS.some(p => p.test(text)) && btn.offsetParent !== null) {
          btn.click();
          return true;
        }
      }
    }

    // Strategy 3: global button search (for iframes where the whole page is consent)
    if (isConsentIframe || !containers.length) {
      const allButtons = document.querySelectorAll('button, a[role="button"], [role="button"]');
      for (const btn of allButtons) {
        const text = (btn.textContent || '').trim();
        if (TEXT_PATTERNS.some(p => p.test(text)) && btn.offsetParent !== null) {
          btn.click();
          return true;
        }
      }
    }

    return false;
  }

  // Try immediately, then observe for late-loading banners
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      setTimeout(tryDismiss, 500);
      setTimeout(tryDismiss, 2000);
    });
  } else {
    setTimeout(tryDismiss, 500);
    setTimeout(tryDismiss, 2000);
  }

  // MutationObserver: catch banners injected after page load
  let dismissed = false;
  const observer = new MutationObserver(() => {
    if (!dismissed && tryDismiss()) {
      dismissed = true;
      observer.disconnect();
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  // Auto-disconnect observer after 10 seconds to avoid overhead
  setTimeout(() => observer.disconnect(), 10000);
})();
"""


async def apply_stealth(context: BrowserContext) -> None:
    """Inject stealth patches and cookie auto-dismiss into a BrowserContext.

    Must be called BEFORE any page navigation.  The init scripts run
    automatically on every page load and iframe creation.

    Args:
        context: The Playwright BrowserContext to patch.
    """
    await context.add_init_script(_STEALTH_JS)
    await context.add_init_script(_COOKIE_DISMISS_JS)
    logger.info("stealth_patches_applied")
