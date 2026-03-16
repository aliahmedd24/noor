# Phase 7 PRD — UI/Frontend & Deployment Readiness

> **Project:** Noor (نور) — AI-Powered Web Navigator for Visually Impaired Users
> **Phase:** 7 of 7
> **Author:** Auto-generated
> **Date:** 2026-03-14
> **Deadline:** 2026-03-16 @ 5:00 PM PDT (Gemini Live Agent Challenge)
> **Status:** Planning

---

## 1. Objective

Transform Noor's bare-bones client into a polished, accessible, demo-ready frontend and ensure the full stack deploys reliably to Google Cloud Run — all within the hackathon deadline.

**Success criteria:**
- A visually compelling, WCAG 2.1 AA-compliant UI that tells Noor's story in seconds
- Reliable one-command deployment to Cloud Run with zero manual steps
- The demo video can be recorded against the deployed URL without local workarounds

---

## 2. Current State Assessment

### Frontend (`client/`)
| Aspect | Current | Gap |
|--------|---------|-----|
| Layout | Single centered column, dark theme | No hero/branding, no visual hierarchy beyond h1 |
| Mic UX | Plain text button, no visual feedback | No pulse animation, no waveform, no recording indicator |
| Transcript | Flat text log | No message bubbles, no distinction between Noor narration vs. tool activity |
| Screenshot feed | None | User cannot see what Noor sees — critical for demo |
| Onboarding | None | First-time user has no guidance |
| Status indicators | Single `#status` text line | No connection badge, no progress spinner for tool execution |
| Responsiveness | Basic `@media (max-width: 480px)` | Untested on tablet/landscape; no touch affordances |
| A11y | ARIA roles present, focus-visible styles, sr-only class | Missing skip-nav, missing landmark regions, missing keyboard shortcuts |
| Error UX | Console-only | No user-facing error toasts or recovery prompts |

### Server / Deployment
| Aspect | Current | Gap |
|--------|---------|-----|
| Dockerfile | Functional (python:3.11-slim + Playwright) | No health check `HEALTHCHECK` instruction, no multi-stage build |
| deploy.sh | ADK CLI primary + gcloud fallback | No pre-flight validation (env vars, API enablement) |
| Terraform | Firestore + IAM + monitoring stubs | No Cloud Run service definition (relies on `adk deploy`) |
| CI/CD | None | No GitHub Actions workflow |
| Session backend | Configurable (memory/vertex/database) | Untested with `vertex` backend on Cloud Run |
| CORS / Security | None configured | FastAPI has no CORS middleware; no CSP headers |
| Static assets | Served via FastAPI `StaticFiles` | No cache headers, no asset fingerprinting |

---

## 3. Scope

### 3.1 In Scope

#### A. Frontend — Accessible Voice-First UI

**A1. Landing / Hero Section**
- Noor logo (Arabic calligraphy "نور" + English tagline)
- One-sentence value prop: "Your Eyes on the Web"
- Prominent "Talk to Noor" CTA with animated mic icon
- Brief 3-step "how it works" strip (Speak → Noor Sees → Noor Acts)

**A2. Voice Interaction UX**
- Pulsing mic button with recording state animation (CSS `@keyframes`)
- Audio waveform visualization (Canvas-based, lightweight)
- Voice activity indicator showing when Noor is speaking vs. listening
- Keyboard shortcut: `Space` to toggle mic (when no input focused)

**A3. Conversation Panel**
- Chat-bubble styled transcript (user messages right-aligned, Noor left-aligned)
- System messages styled as inline notices (italic, muted)
- Tool activity indicators: "Noor is navigating to google.com..." with spinner
- Auto-scroll with "scroll to bottom" affordance when user scrolls up
- Timestamp on each message group

**A4. Live Screenshot Feed**
- Side panel (desktop) or expandable drawer (mobile) showing latest browser screenshot
- Updated after every navigation/vision tool call
- Annotated with bounding boxes when Noor identifies interactive elements
- Toggle: show/hide screenshot panel (default: visible on desktop, hidden on mobile)
- Requires server to emit screenshot data over WebSocket

**A5. Onboarding & Help**
- First-visit modal/overlay explaining Noor's capabilities
- Example prompts as clickable chips: "Go to CNN.com", "Search for flights to Tokyo", "Fill out this form"
- `?` button opening a help panel with keyboard shortcuts and tips
- Dismissable, remembers preference via `localStorage`

**A6. Settings Panel**
- Voice speed preference (slow/normal/fast) — stored in session state
- High-contrast mode toggle (already dark, add light theme option)
- Text size adjustment (small/medium/large)
- Persist via `localStorage`, sync to ADK session state on connect

**A7. Accessibility Hardening**
- Skip-nav link as first focusable element
- Proper landmark regions: `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`
- ARIA live regions: `polite` for transcript, `assertive` for errors
- Focus management: return focus to input after Noor responds
- Screen reader announcements for tool activity ("Noor is taking a screenshot")
- Reduced-motion media query: disable animations when `prefers-reduced-motion`
- Color contrast ratios verified ≥ 4.5:1 (AA) for all text

**A8. Error & Offline UX**
- Toast notifications for connection errors with retry button
- Graceful degradation when mic is denied (text-only mode with clear messaging)
- Offline detection banner: "You're offline. Noor will reconnect when you're back."
- WebSocket reconnection with exponential backoff (replace current fixed 3s retry)

#### B. Server Enhancements for Frontend

**B1. Screenshot Streaming**
- After every `take_screenshot` or vision tool call, emit a WebSocket event:
  ```json
  {"type": "screenshot", "data": "<base64-jpeg>", "annotations": [...]}
  ```
- Annotations include bounding boxes from `VisionResult.interactive_elements`
- Throttle to max 1 screenshot per 2 seconds to avoid flooding

**B2. Tool Activity Events**
- Emit structured events for tool lifecycle:
  ```json
  {"type": "tool_start", "tool": "navigate_to_url", "args": {"url": "..."}}
  {"type": "tool_end", "tool": "navigate_to_url", "status": "success"}
  ```
- Frontend uses these to show contextual spinners/messages

**B3. CORS & Security Headers**
- Add `CORSMiddleware` configured for the deployed Cloud Run URL + `localhost`
- Add security headers middleware: `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`
- Rate-limit WebSocket connections per IP (10 connections/minute)

**B4. Static Asset Optimization**
- Add `Cache-Control` headers for static files (1 hour for CSS/JS, 1 day for images)
- Gzip compression middleware

#### C. Deployment Readiness

**C1. Dockerfile Hardening**
- Multi-stage build: builder stage for pip install, slim runtime stage
- `HEALTHCHECK` instruction pointing to `/health`
- Non-root user (`noor:noor`)
- `.dockerignore` for tests, docs, .git, __pycache__, .env

**C2. Pre-flight Validation Script**
- `scripts/preflight.sh`: checks all required env vars, GCP API enablement, Docker availability
- Run automatically as first step in `deploy.sh`
- Clear error messages for each failure

**C3. GitHub Actions CI/CD**
- `.github/workflows/ci.yml`:
  - Trigger: push to `main`, PR to `main`
  - Jobs: lint (`ruff`), type-check (`pyright`), unit tests (`pytest`), Docker build
  - Skip Playwright install on CI (mock browser in tests)
- `.github/workflows/deploy.yml`:
  - Trigger: manual dispatch or tag push (`v*`)
  - Authenticate to GCP via Workload Identity Federation
  - Build and push to Artifact Registry
  - Deploy to Cloud Run via `gcloud run deploy`

**C4. Environment Configuration**
- Validate `.env.example` matches all variables referenced in code
- Add `NOOR_ALLOWED_ORIGINS` env var for CORS configuration
- Add `NOOR_RATE_LIMIT` env var (default: 10 req/min)
- Document production vs. dev env var differences in `.env.example`

**C5. Cloud Run Service Configuration**
- `--memory=2Gi --cpu=2` (Playwright + Chromium needs this)
- `--min-instances=1` for demo (avoid cold start during recording)
- `--session-affinity` for WebSocket sticky sessions
- `--timeout=300` for long-running voice sessions
- Custom domain mapping (if available)

**C6. Terraform Updates**
- Add Cloud Run service resource (alternative to `adk deploy` for reproducibility)
- Add Artifact Registry repository for Docker images
- Add Cloud Run IAM binding for `allUsers` (unauthenticated access for demo)

### 3.2 Out of Scope
- Native mobile app or PWA (service worker, manifest)
- User authentication / login
- Multi-language UI (English only)
- Analytics / telemetry dashboard
- Custom domain SSL provisioning
- Load testing / performance benchmarking
- Production monitoring alerting (Terraform has stubs only)

---

## 4. Technical Design

### 4.1 Frontend Architecture

```
client/
├── index.html              # Shell: landmark regions, skip-nav, script/style refs
├── styles.css              # Design tokens, component styles, a11y utilities
├── app.js                  # Main entry: WebSocket, event routing, state
├── components/
│   ├── mic-button.js       # Mic toggle + pulse animation + waveform canvas
│   ├── transcript.js       # Chat-bubble renderer + auto-scroll
│   ├── screenshot.js       # Screenshot panel + annotation overlay
│   ├── toast.js            # Error/info toast notifications
│   ├── onboarding.js       # First-visit overlay + example chips
│   └── settings.js         # Preferences panel + localStorage sync
└── assets/
    ├── noor-logo.svg       # Logo
    └── icons/              # Mic, settings, help, close SVG icons
```

**No build step.** Vanilla JS with ES modules (`<script type="module">`). This keeps the frontend zero-dependency and avoids toolchain complexity for the hackathon.

### 4.2 WebSocket Protocol Extensions

Current protocol (unchanged):
- Client → Server: binary PCM audio, JSON `{"type": "text", "content": "..."}`
- Server → Client: binary PCM audio, JSON ADK events

New events (server → client):
```
{"type": "screenshot", "data": "<base64>", "annotations": [...]}
{"type": "tool_start", "tool": "<name>", "args": {...}}
{"type": "tool_end", "tool": "<name>", "status": "success|error", "duration_ms": 1234}
{"type": "status", "message": "Navigating to google.com..."}
{"type": "error", "code": "mic_denied|ws_error|server_error", "message": "..."}
```

New events (client → server):
```
{"type": "settings", "voice_speed": "normal", "text_size": "medium"}
```

### 4.3 Deployment Pipeline

```
Developer pushes to main
        │
        ▼
GitHub Actions CI ──────────────────────────────────┐
  ├─ ruff lint                                      │
  ├─ pytest (mocked browser)                        │
  └─ docker build (verify Dockerfile)               │
        │                                           │
        ▼ (on tag push v*)                          │
GitHub Actions Deploy                               │
  ├─ gcloud auth (Workload Identity)                │
  ├─ docker build + push to Artifact Registry       │
  └─ gcloud run deploy                              │
        │                                           │
        ▼                                           │
Cloud Run Service                                   │
  ├─ /health → 200                                  │
  ├─ / → client UI                                  │
  └─ /ws/{user}/{session} → bidi streaming          │
```

---

## 5. Implementation Plan

### Sprint 1 — Core UI Polish (Day 1 morning: ~4 hours)

| # | Task | Files | Est. |
|---|------|-------|------|
| 1.1 | Restructure `index.html` with landmark regions, skip-nav, module scripts | `client/index.html` | 30m |
| 1.2 | Design system: CSS custom properties, component classes, dark/light themes | `client/styles.css` | 1h |
| 1.3 | Chat-bubble transcript component | `client/components/transcript.js` | 45m |
| 1.4 | Mic button with pulse animation + waveform visualization | `client/components/mic-button.js` | 1h |
| 1.5 | Toast notification component | `client/components/toast.js` | 30m |
| 1.6 | Refactor `app.js` to use ES modules + new event types | `client/app.js` | 45m |

### Sprint 2 — Screenshot Feed & Rich Events (Day 1 afternoon: ~3 hours)

| # | Task | Files | Est. |
|---|------|-------|------|
| 2.1 | Server: emit screenshot events after vision tool calls | `noor_agent/callbacks.py`, `server/main.py` | 45m |
| 2.2 | Server: emit `tool_start`/`tool_end` events | `noor_agent/callbacks.py`, `server/main.py` | 30m |
| 2.3 | Screenshot panel component with annotation overlay | `client/components/screenshot.js` | 1h |
| 2.4 | Tool activity indicators in transcript | `client/components/transcript.js` | 30m |
| 2.5 | WebSocket reconnection with exponential backoff | `client/app.js` | 20m |

### Sprint 3 — Onboarding, Settings & A11y (Day 1 evening: ~2 hours)

| # | Task | Files | Est. |
|---|------|-------|------|
| 3.1 | Onboarding overlay with example prompt chips | `client/components/onboarding.js` | 45m |
| 3.2 | Settings panel (voice speed, text size, theme) | `client/components/settings.js` | 45m |
| 3.3 | Keyboard shortcuts (Space for mic, Escape to close modals) | `client/app.js` | 20m |
| 3.4 | A11y audit pass: focus management, ARIA, reduced-motion | All client files | 30m |

### Sprint 4 — Deployment Hardening (Day 2 morning: ~3 hours)

| # | Task | Files | Est. |
|---|------|-------|------|
| 4.1 | Dockerfile: multi-stage build, non-root user, HEALTHCHECK | `Dockerfile` | 30m |
| 4.2 | `.dockerignore` | `.dockerignore` | 10m |
| 4.3 | CORS + security headers middleware | `server/main.py` | 30m |
| 4.4 | Pre-flight validation script | `scripts/preflight.sh` | 30m |
| 4.5 | Update `deploy.sh` with pre-flight + Cloud Run flags | `scripts/deploy.sh` | 20m |
| 4.6 | GitHub Actions CI workflow | `.github/workflows/ci.yml` | 30m |
| 4.7 | GitHub Actions deploy workflow | `.github/workflows/deploy.yml` | 30m |
| 4.8 | Update `.env.example` with all new vars | `.env.example` | 15m |

### Sprint 5 — Integration Test & Demo Prep (Day 2 afternoon: ~2 hours)

| # | Task | Files | Est. |
|---|------|-------|------|
| 5.1 | End-to-end test: deploy to Cloud Run, verify health + WebSocket | Manual | 30m |
| 5.2 | Test all 3 demo scenarios against deployed URL | Manual | 30m |
| 5.3 | Screenshot/logo assets (Noor branding) | `client/assets/` | 20m |
| 5.4 | Update `README.md` with deployment instructions + screenshots | `README.md` | 20m |
| 5.5 | Final a11y pass with screen reader (NVDA/JAWS) | Manual | 20m |

---

## 6. Dependencies & Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Playwright Chromium fails on Cloud Run | Medium | High | Dockerfile already works; test early with `docker run` locally |
| Gemini Live API latency makes demo sluggish | Medium | High | Pre-warm with `--min-instances=1`; optimize screenshot size |
| WebSocket drops on Cloud Run (default 5min timeout) | Low | Medium | Set `--timeout=300`, implement client-side heartbeat |
| Audio playback fails on demo browser | Low | Medium | Test in Chrome + Edge; fallback to text transcript |
| Cold start exceeds demo patience | Medium | Medium | `--min-instances=1` eliminates cold starts for $$ |
| CORS blocks deployed frontend | Low | Low | Test CORS config before demo; have fallback `--allow-unauthenticated` |

---

## 7. Acceptance Criteria

- [ ] UI renders correctly on Chrome/Edge desktop (1920x1080 and 1280x800)
- [ ] UI renders correctly on mobile viewport (375x812)
- [ ] Mic button shows recording animation when active
- [ ] Transcript displays chat bubbles with user/Noor distinction
- [ ] Screenshot panel shows latest browser view with annotations
- [ ] Onboarding overlay appears on first visit, dismissable
- [ ] Settings persist across page reloads via localStorage
- [ ] All interactive elements are keyboard-navigable (Tab, Enter, Space, Escape)
- [ ] Screen reader (NVDA) can navigate all content and receives live announcements
- [ ] `docker build && docker run` works locally with `.env`
- [ ] `scripts/deploy.sh` deploys to Cloud Run without manual steps
- [ ] `/health` returns 200 on deployed service
- [ ] WebSocket voice conversation works on deployed URL
- [ ] Text fallback input works when mic is denied
- [ ] Reconnects automatically after WebSocket disconnect
- [ ] No console errors in steady state

---

## 8. Demo Alignment

The 3 demo scenarios from the hackathon brief:

1. **Flight Search** — User says "Find me flights from SFO to Tokyo next month"
   - UI shows: mic pulse → Noor narrates actions → screenshot panel updates → results summarized in chat
2. **News Reading** — User says "Go to CNN and read me the top headlines"
   - UI shows: navigation activity → screenshot feed → Noor reads content aloud → transcript captures summary
3. **Form Filling** — User says "Fill out this contact form with my info"
   - UI shows: Noor identifies form fields → type/click activity → confirmation in chat

The frontend must make these scenarios visually compelling in a ≤4 minute video recording.
