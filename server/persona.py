"""Noor voice persona configuration for Gemini Live API."""

from google.genai import types

# Available voices: Puck, Charon, Kore, Fenrir, Aoede, Leda, Orus, Zephyr
NOOR_VOICE = "Leda"  # Warm, clear voice suitable for accessibility narration

# Live API model for streaming (check latest at ADK docs)
# Dev (AI Studio): gemini-2.5-flash-native-audio-preview-12-2025
# Prod (Vertex AI): gemini-live-2.5-flash-native-audio
LIVE_MODEL_DEV = "gemini-2.5-flash-native-audio-preview-12-2025"
LIVE_MODEL_PROD = "gemini-live-2.5-flash-native-audio"


def build_speech_config(voice_name: str = NOOR_VOICE) -> types.SpeechConfig:
    """Build a SpeechConfig for the Gemini Live API.

    Args:
        voice_name: One of the available Gemini voices.

    Returns:
        A SpeechConfig ready to pass into RunConfig.
    """
    return types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=voice_name,
            )
        )
    )
