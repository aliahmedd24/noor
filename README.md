# NOOR — COMPLETE PROJECT PRD

## AI-Powered Web Navigator for Visually Impaired Users

### Hackathon: Gemini Live Agent Challenge | Category: UI Navigator ☸️

---

## PRD Document Index

| Phase | File | Focus | Dependencies |
|-------|------|-------|-------------|
| **Phase 0** | `PHASE-0-FOUNDATION.md` | Project setup, directory structure, CLAUDE.md, Dockerfile, dependencies | None |
| **Phase 1** | `PHASE-1-BROWSER-ENGINE.md` | Playwright browser manager, action executor, screenshot capture, ADK browser tools | Phase 0 |
| **Phase 2** | `PHASE-2-VISION-ENGINE.md` | Gemini multimodal screen analysis, scene description models, vision prompts, ADK vision tools | Phase 0, 1 |
| **Phase 3** | `PHASE-3-ADK-AGENTS.md` | Multi-agent hierarchy (Orchestrator + 3 sub-agents), session state, agent instructions | Phase 0, 1, 2 |
| **Phase 4** | `PHASE-4-VOICE-INTERFACE.md` | FastAPI server, Gemini Live API streaming, WebSocket audio, accessible client UI | Phase 0, 1, 2, 3 |
| **Phase 5** | `PHASE-5-GCP-DEPLOYMENT.md` | Terraform IaC, Cloud Run, Firestore, Secret Manager, deployment scripts, monitoring | Phase 0-4 |
| **Phase 6** | `PHASE-6-INTEGRATION-DEMO.md` | Integration tests, demo scenarios, video script, architecture diagram, submission checklist | Phase 0-5 |

---

## Recommended Build Order

### Sprint 1 (Days 1-2): Foundation + Browser Engine
- Phase 0: Project structure, dependencies, CLAUDE.md
- Phase 1: BrowserManager, actions, screenshot, browser tools
- **Milestone:** Can navigate websites and take screenshots programmatically

### Sprint 2 (Days 3-4): Vision + Agents
- Phase 2: ScreenAnalyzer, vision prompts, vision tools
- Phase 3: All 4 ADK agents, orchestration, session state
- **Milestone:** Text-based agent interaction works via `adk run`

### Sprint 3 (Days 5-6): Voice + Deployment
- Phase 4: FastAPI server, WebSocket streaming, client UI
- Phase 5: Terraform, Cloud Run deployment, Firestore
- **Milestone:** Voice interaction works locally and deployed on GCP

### Sprint 4 (Day 7): Polish + Submit
- Phase 6: Integration testing, demo rehearsal, video recording, blog post
- **Milestone:** Submission complete on Devpost

---

## Tech Stack Summary

```
┌─────────────────────────────────────────────────────┐
│  AGENT LAYER          Google ADK (Python)            │
│  ├─ NoorOrchestrator  LlmAgent (root)               │
│  ├─ ScreenVisionAgent LlmAgent + vision tools       │
│  ├─ NavigatorAgent    LlmAgent + browser tools       │
│  └─ PageSummarizer    LlmAgent + content tools       │
├─────────────────────────────────────────────────────┤
│  MODEL LAYER                                         │
│  ├─ Gemini 2.5 Flash       Vision + Language         │
│  └─ Gemini Live API        Streaming Audio (Bidi)    │
├─────────────────────────────────────────────────────┤
│  BROWSER LAYER        Playwright (Async Python)      │
│  └─ Headless Chromium   1280x800 viewport            │
├─────────────────────────────────────────────────────┤
│  SERVER LAYER         FastAPI + WebSocket             │
├─────────────────────────────────────────────────────┤
│  CLIENT LAYER         HTML/JS (Accessibility-first)  │
├─────────────────────────────────────────────────────┤
│  CLOUD LAYER          Google Cloud Platform           │
│  ├─ Cloud Run          Container hosting              │
│  ├─ Vertex AI          Model API                     │
│  ├─ Firestore          User data                     │
│  ├─ Secret Manager     Credentials                   │
│  ├─ Cloud Logging      Observability                 │
│  └─ Terraform          Infrastructure-as-Code         │
└─────────────────────────────────────────────────────┘
```

---

## Judging Criteria Mapping

| Criterion | Weight | How Noor Scores |
|-----------|--------|-----------------|
| **Innovation & Multimodal UX** | 40% | Voice-first UI for blind users breaks the text-box paradigm completely. Agent sees (Gemini vision), hears (Live API audio input), speaks (Live API audio output). Context-aware narration throughout. |
| **Technical Implementation** | 30% | ADK multi-agent with 4 specialized agents, Vertex AI for model serving, Cloud Run deployment, Firestore for state, Terraform IaC, structured logging. |
| **Demo & Presentation** | 30% | 3 compelling real-world scenarios (flights, news, forms), clear architecture diagram, GCP deployment proof, working software on camera. |
| **[Bonus] Blog post** | +0.6 | Published dev.to post with #GeminiLiveAgentChallenge |
| **[Bonus] IaC deployment** | +0.2 | Full Terraform configuration in `infra/` |
| **[Bonus] GDG membership** | +0.2 | Active GDG profile linked |

**Max possible score: 6.0 / 6.0**

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Gemini vision misidentifies elements | High | Use coordinate grid overlay, fallback to text-based clicking |
| Live API latency > 5s | Medium | Narrate "processing" filler, pre-warm connections |
| Playwright fails in Cloud Run container | High | Test Dockerfile early, include all system deps, `--no-sandbox` flag |
| WebSocket drops on Cloud Run | Medium | Session affinity enabled, client auto-reconnects |
| Demo scenarios fail on camera | High | Pre-test all scenarios, have text-mode fallback, warm browser cache |
| Scope creep | High | Stick to 3 demo scenarios, optimize those, ignore edge cases |
