# Noor — System Architecture

> AI-powered web navigator for visually impaired users.

## Agent Architecture

```
User (Voice) <-> FastAPI WebSocket <-> ADK Streaming Runner
                                          |
                                   NoorOrchestrator (root)
                                     /       |        \
                            ScreenVision  Navigator  PageSummarizer
                               Agent       Agent       Agent
                                 |           |           |
                            Gemini Vision  Playwright  Gemini LLM
                            (screenshots)  (browser)   (content)
```

## Data Flow

1. User speaks -> AudioWorklet captures PCM -> WebSocket sends audio chunks
2. ADK Streaming routes audio to Gemini Live API
3. Orchestrator interprets intent, delegates to sub-agent
4. Sub-agent uses tools (browser, vision, content extraction)
5. Results flow back through orchestrator -> Gemini Live API -> audio response
6. User hears narrated result

## Shared State Keys

| Key | Writer | Reader |
|-----|--------|--------|
| `vision_analysis` | ScreenVisionAgent | Navigator, Summarizer, Orchestrator |
| `navigation_result` | NavigatorAgent | Orchestrator |
| `page_summary` | PageSummarizerAgent | Orchestrator |
| `current_url` | browser tools | All agents |
| `current_title` | browser tools | All agents |
