"""Noor voice persona configuration for Gemini Live API."""

# Available voices: Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, Zephyr
NOOR_VOICE = "Leda"  # Warm, clear voice suitable for accessibility narration

# Live API model for streaming (check latest at ADK docs)
# Dev (AI Studio): gemini-2.5-flash-native-audio-preview-12-2025
# Prod (Vertex AI): gemini-live-2.5-flash-native-audio
LIVE_MODEL_DEV = "gemini-2.5-flash-native-audio-preview-12-2025"
LIVE_MODEL_PROD = "gemini-live-2.5-flash-native-audio"
