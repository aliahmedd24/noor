# PHASE 3: ADK MULTI-AGENT SYSTEM

## Objective

Build the multi-agent orchestration layer using Google ADK. This is the brain of Noor — a hierarchy of specialized agents that collaborate to understand user intent, analyze the screen, plan actions, execute browser interactions, and narrate results. This phase directly addresses the **Technical Implementation & Agent Architecture (30%)** judging criterion.

---

## 3.1 — AGENT ARCHITECTURE OVERVIEW

```
                    ┌─────────────────────────┐
                    │   NoorOrchestrator       │
                    │   (Root LLM Agent)       │
                    │   Model: gemini-2.5-flash│
                    │                          │
                    │   Role: Conversation      │
                    │   management, intent      │
                    │   routing, narration      │
                    └────┬──────┬──────┬───────┘
                         │      │      │
              ┌──────────┘      │      └──────────┐
              ▼                 ▼                  ▼
    ┌─────────────────┐ ┌──────────────┐ ┌────────────────┐
    │ ScreenVision    │ │ Navigator    │ │ PageSummarizer │
    │ Agent           │ │ Agent        │ │ Agent          │
    │                 │ │              │ │                │
    │ Analyzes screen-│ │ Plans and    │ │ Extracts and   │
    │ shots, describes│ │ executes     │ │ summarizes page│
    │ page elements   │ │ browser      │ │ content for    │
    │ and layout      │ │ actions      │ │ reading aloud  │
    └─────────────────┘ └──────────────┘ └────────────────┘
```

### Agent Roles

| Agent | ADK Type | Model | Tools | Purpose |
|-------|----------|-------|-------|---------|
| **NoorOrchestrator** | `LlmAgent` (root) | `gemini-2.5-flash` | None (delegates) | Conversation management, user intent parsing, response narration, delegates to sub-agents |
| **ScreenVisionAgent** | `LlmAgent` (sub) | `gemini-2.5-flash` | `analyze_current_page`, `describe_page_aloud`, `find_and_click` | Screenshot analysis, page description, element identification |
| **NavigatorAgent** | `LlmAgent` (sub) | `gemini-2.5-flash` | `navigate_to_url`, `click_at_coordinates`, `click_element_by_text`, `type_into_field`, `scroll_down`, `scroll_up`, `press_enter`, `press_tab`, `go_back_in_browser` | Browser action planning and execution |
| **PageSummarizerAgent** | `LlmAgent` (sub) | `gemini-2.5-flash` | `analyze_current_page`, `describe_page_aloud`, `scroll_down` | Content extraction, article reading, structured summarization |

### Delegation Strategy

The Orchestrator uses **LLM-driven delegation** (ADK's automatic transfer based on sub-agent descriptions). This means the Gemini model powering the Orchestrator reads the `description` field of each sub-agent and decides which one to transfer control to based on the user's message.

**This is the simplest and most ADK-native approach** — no custom routing logic needed.

---

## 3.2 — ORCHESTRATOR AGENT (`src/agents/orchestrator.py`)

The root agent — Noor's conversational personality.

### Agent Definition

```python
from google.adk.agents import LlmAgent
from pathlib import Path

# Load instruction prompt from file
ORCHESTRATOR_INSTRUCTION = (Path(__file__).parent / "instructions" / "orchestrator.txt").read_text()

orchestrator_agent = LlmAgent(
    name="NoorOrchestrator",
    model="gemini-2.5-flash",
    description=(
        "Noor is the main conversational agent — a warm, patient AI assistant "
        "for visually impaired users navigating the web. Noor manages the "
        "conversation, understands what the user wants to do, and coordinates "
        "with specialist agents to analyze screens, navigate websites, and "
        "read content aloud. Noor always narrates what is happening."
    ),
    instruction=ORCHESTRATOR_INSTRUCTION,
    sub_agents=[],  # Populated after sub-agent definitions
)
```

### Orchestrator Instruction Prompt (`src/agents/instructions/orchestrator.txt`)

```text
You are Noor (نور — "Light"), an AI assistant designed to help visually impaired users navigate the web independently. You are the user's eyes and hands on the internet.

## Your Personality
- Warm, patient, and encouraging
- Concise but descriptive — never say "click here", always describe what things are
- Proactive — anticipate what information the user needs
- Honest about limitations — if something is unclear on screen, say so

## Your Capabilities
You coordinate with three specialist agents:
1. **ScreenVisionAgent**: Sees and analyzes the current web page. Use this when you need to understand what's on screen.
2. **NavigatorAgent**: Controls the browser. Use this when you need to click, type, scroll, or navigate.
3. **PageSummarizerAgent**: Reads and summarizes page content. Use this when the user wants to know what a page says.

## Conversation Flow
For EVERY user request, follow this pattern:
1. **Acknowledge** the request immediately ("Sure, let me navigate to Google for you.")
2. **Delegate** to the appropriate specialist agent
3. **Narrate** the result ("I've opened Google. I can see the search box in the center of the page. What would you like to search for?")

## Rules
- ALWAYS narrate what you see and what you're doing — the user cannot see the screen
- When describing a page, prioritize: (1) what the page IS, (2) key content, (3) what actions are available
- When listing items (search results, products, etc.), number them: "The first result is..., the second is..."
- For form fields, read the label and any placeholder text
- If a cookie banner appears, offer to dismiss it
- If the page has an error, describe the error message
- NEVER say "I see a button at coordinates (x, y)" — describe it naturally: "I see a blue Sign In button in the top right corner"
- If you're unsure about an element, take another screenshot for a closer look
- When an action is complete, always confirm: "Done! The search results are now showing..."

## Common Flows
- **"Go to [website]"**: Navigate → take screenshot → describe the page
- **"Search for [topic]"**: Navigate to search engine → type → submit → describe results
- **"Click [something]"**: Analyze page → find element → click → describe result
- **"Read this page"**: Analyze page → extract content → summarize aloud
- **"Fill in [form field] with [value]"**: Analyze page → find field → type → confirm
- **"What's on the screen?"**: Analyze page → describe layout and content
- **"Go back"**: Navigate back → describe the previous page
```

---

## 3.3 — SCREEN VISION AGENT (`src/agents/vision_agent.py`)

```python
from google.adk.agents import LlmAgent
from src.tools.vision_tools import (
    analyze_current_page,
    describe_page_aloud,
    find_and_click,
)

vision_agent = LlmAgent(
    name="ScreenVisionAgent",
    model="gemini-2.5-flash",
    description=(
        "Specialist agent for visual analysis of web pages. Captures screenshots "
        "and uses AI vision to understand page layout, identify interactive elements "
        "(buttons, links, forms, menus), describe images, and read text content. "
        "Use this agent when you need to SEE what is currently on the screen or "
        "find a specific element to interact with."
    ),
    instruction=(
        "You are Noor's visual analysis system. When invoked:\n"
        "1. Use 'analyze_current_page' to capture and analyze the current screenshot\n"
        "2. Report back with a clear description of what you see\n"
        "3. If asked to find a specific element, use 'find_and_click' with a description\n"
        "4. If asked to describe the page for the user, use 'describe_page_aloud'\n\n"
        "Always include the coordinates of interactive elements you mention.\n"
        "Store your analysis in the session state for other agents to reference.\n"
        "Be precise about element positions — say 'top-right', 'center', 'below the heading', etc."
    ),
    tools=[analyze_current_page, describe_page_aloud, find_and_click],
    output_key="vision_analysis",
)
```

---

## 3.4 — NAVIGATOR AGENT (`src/agents/navigator_agent.py`)

```python
from google.adk.agents import LlmAgent
from src.tools.browser_tools import (
    navigate_to_url,
    click_at_coordinates,
    click_element_by_text,
    type_into_field,
    scroll_down,
    scroll_up,
    press_enter,
    press_tab,
    go_back_in_browser,
    take_screenshot_of_page,
)

navigator_agent = LlmAgent(
    name="NavigatorAgent",
    model="gemini-2.5-flash",
    description=(
        "Specialist agent for browser control and web navigation. Executes actions "
        "like clicking buttons, typing text, scrolling, navigating to URLs, and "
        "going back/forward. Use this agent when you need to INTERACT with the "
        "web page — clicking, typing, scrolling, or navigating to a new URL."
    ),
    instruction=(
        "You are Noor's browser controller. When invoked:\n"
        "1. Check if the vision analysis in session state has the information you need\n"
        "   (look for 'vision_analysis' in the session state)\n"
        "2. Execute the requested browser action using the appropriate tool\n"
        "3. After executing an action, take a screenshot to confirm the result\n"
        "4. Report what happened (success/failure, what changed on the page)\n\n"
        "Action Guidelines:\n"
        "- To click: Prefer 'click_at_coordinates' when you have coordinates from vision analysis.\n"
        "  Fall back to 'click_element_by_text' when coordinates are uncertain.\n"
        "- To type: Use 'type_into_field' with coordinates to click the field first.\n"
        "- After typing in search boxes: Use 'press_enter' to submit.\n"
        "- To see more content: Use 'scroll_down' or 'scroll_up'.\n"
        "- To go to a URL: Use 'navigate_to_url' with the full https:// URL.\n"
        "- After any action: Use 'take_screenshot_of_page' to see the result.\n\n"
        "Common URL patterns:\n"
        "- Google: https://www.google.com\n"
        "- Google search: https://www.google.com/search?q={query}\n\n"
        "IMPORTANT: Always report the outcome of your actions."
    ),
    tools=[
        navigate_to_url,
        click_at_coordinates,
        click_element_by_text,
        type_into_field,
        scroll_down,
        scroll_up,
        press_enter,
        press_tab,
        go_back_in_browser,
        take_screenshot_of_page,
    ],
    output_key="navigation_result",
)
```

---

## 3.5 — PAGE SUMMARIZER AGENT (`src/agents/summarizer_agent.py`)

```python
from google.adk.agents import LlmAgent
from src.tools.vision_tools import analyze_current_page, describe_page_aloud
from src.tools.browser_tools import scroll_down

summarizer_agent = LlmAgent(
    name="PageSummarizerAgent",
    model="gemini-2.5-flash",
    description=(
        "Specialist agent for reading and summarizing web page content. Extracts "
        "the main text, article body, search results, or product details from "
        "the current page and presents them in a clear, concise format suitable "
        "for reading aloud. Use this agent when the user wants to KNOW what a "
        "page says — reading articles, reviewing search results, or understanding "
        "form content."
    ),
    instruction=(
        "You are Noor's content reader. When invoked:\n"
        "1. Use 'analyze_current_page' to see what's on the page\n"
        "2. Summarize the content based on what the user wants:\n"
        "   - For articles: Read the headline, key points, and conclusion\n"
        "   - For search results: List the top results with titles and snippets\n"
        "   - For product pages: Name, price, rating, key features\n"
        "   - For forms: List all fields and their current values\n"
        "3. If the page is long, use 'scroll_down' to see more content\n"
        "4. Present content in a natural, spoken format\n\n"
        "Reading Guidelines:\n"
        "- Number items in lists: 'First result... Second result...'\n"
        "- Skip navigation, footers, ads, and cookie banners\n"
        "- For prices, read the full amount: 'one hundred and twenty euros'\n"
        "- For images, describe what they show\n"
        "- Keep summaries to 3-5 sentences unless the user asks for more detail"
    ),
    tools=[analyze_current_page, describe_page_aloud, scroll_down],
    output_key="page_summary",
)
```

---

## 3.6 — ROOT AGENT ASSEMBLY (`src/agents/agent.py`)

This is the ADK entry point. The file MUST export `root_agent`.

```python
"""
Noor Agent — Root ADK agent definition.

This module assembles the multi-agent hierarchy and exports the root_agent
that ADK uses as the entry point for all interactions.

Architecture:
    NoorOrchestrator (root)
    ├── ScreenVisionAgent
    ├── NavigatorAgent
    └── PageSummarizerAgent
"""
from src.agents.orchestrator import orchestrator_agent
from src.agents.vision_agent import vision_agent
from src.agents.navigator_agent import navigator_agent
from src.agents.summarizer_agent import summarizer_agent

# Assemble the agent hierarchy
orchestrator_agent.sub_agents = [
    vision_agent,
    navigator_agent,
    summarizer_agent,
]

# Export as root_agent (ADK convention)
root_agent = orchestrator_agent
```

### `src/agents/__init__.py`

```python
"""Noor ADK agents package. Exports root_agent for ADK framework."""
from src.agents.agent import root_agent

__all__ = ["root_agent"]
```

---

## 3.7 — SESSION STATE MANAGEMENT

ADK agents share state through the session state dictionary. Here's the state schema Noor uses:

### State Keys

| Key | Set By | Read By | Type | Purpose |
|-----|--------|---------|------|---------|
| `vision_analysis` | ScreenVisionAgent (`output_key`) | NavigatorAgent, PageSummarizerAgent | str (JSON) | Last vision analysis result |
| `navigation_result` | NavigatorAgent (`output_key`) | NoorOrchestrator | str | Result of last browser action |
| `page_summary` | PageSummarizerAgent (`output_key`) | NoorOrchestrator | str | Last content summary |
| `current_url` | browser tools | All agents | str | Current page URL |
| `current_title` | browser tools | All agents | str | Current page title |
| `user_preferences` | user tools | All agents | dict | User settings (verbosity, speed) |

### How State Flows

1. User says: "Go to BBC News and read me the top headlines"
2. **NoorOrchestrator** interprets intent → delegates to NavigatorAgent
3. **NavigatorAgent** calls `navigate_to_url("https://www.bbc.com/news")` → takes screenshot → stores result in `navigation_result`
4. Control returns to **NoorOrchestrator** → delegates to PageSummarizerAgent
5. **PageSummarizerAgent** calls `analyze_current_page()` → stores summary in `page_summary`
6. Control returns to **NoorOrchestrator** → narrates the summary to the user

---

## 3.8 — LOCAL TESTING WITH ADK CLI

ADK provides built-in tools for testing agents locally:

```bash
# Run in terminal mode (text-based)
cd noor
adk run src/agents

# Run with web UI (development only)
adk web src/agents

# Run with streaming (voice + video)
adk web src/agents --streaming
```

**Important:** The agent directory must contain `__init__.py` that exports `root_agent`.

For the `adk web` dev UI:
- Select "NoorOrchestrator" from the agent dropdown
- Test conversations in the text box
- Inspect Events tab to see agent transfers and tool calls
- Use the streaming mode to test voice interaction

---

## 3.9 — IMPLEMENTATION ORDER

1. **`src/agents/instructions/orchestrator.txt`** — Orchestrator system prompt
2. **`src/agents/orchestrator.py`** — NoorOrchestrator LlmAgent
3. **`src/agents/vision_agent.py`** — ScreenVisionAgent
4. **`src/agents/navigator_agent.py`** — NavigatorAgent
5. **`src/agents/summarizer_agent.py`** — PageSummarizerAgent
6. **`src/agents/agent.py`** — Root agent assembly
7. **`src/agents/__init__.py`** — Package exports
8. **Test with `adk run`** — Verify text-based interaction works

---

## 3.10 — ACCEPTANCE CRITERIA

- [ ] `adk run src/agents` starts successfully and accepts text input
- [ ] User message "Go to google.com" → Orchestrator delegates to NavigatorAgent → browser navigates
- [ ] User message "What's on the screen?" → Orchestrator delegates to ScreenVisionAgent → screenshot analyzed
- [ ] User message "Read the search results" → Orchestrator delegates to PageSummarizerAgent → content read
- [ ] Agent transfers are visible in ADK's Events inspector (or terminal logs)
- [ ] Session state keys (`vision_analysis`, `navigation_result`, `page_summary`) are populated correctly
- [ ] Orchestrator narrates results in warm, descriptive voice appropriate for blind users
- [ ] Multi-step flow works: "Search Google for weather in Bremen" → navigate → type → enter → read results
- [ ] Error handling: graceful response when a page fails to load or element not found

---

## 3.11 — AGENT EVALUATION (`tests/eval/`)

ADK supports built-in evaluation using `.evalset.json` files.

### `tests/eval/navigation_eval.json`

```json
[
  {
    "query": "Go to google.com",
    "expected_tool_use": ["navigate_to_url"],
    "expected_response_contains": ["Google", "search"]
  },
  {
    "query": "What's on the screen?",
    "expected_tool_use": ["analyze_current_page"],
    "expected_response_contains": ["page", "see"]
  },
  {
    "query": "Search for cheap flights to Berlin",
    "expected_tool_use": ["navigate_to_url", "type_into_field", "press_enter"],
    "expected_response_contains": ["search", "results"]
  },
  {
    "query": "Click the first search result",
    "expected_tool_use": ["find_and_click"],
    "expected_response_contains": ["clicked", "opened"]
  },
  {
    "query": "Go back to the previous page",
    "expected_tool_use": ["go_back_in_browser"],
    "expected_response_contains": ["back", "previous"]
  }
]
```

Run evaluations with:
```bash
adk eval src/agents tests/eval/navigation_eval.json
```
