"""Noor application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings populated from environment variables.

    Attributes:
        google_cloud_project: GCP project ID.
        google_cloud_location: GCP region for Vertex AI.
        google_genai_use_vertexai: Use Vertex AI (TRUE) or AI Studio (FALSE).
        google_api_key: Gemini API key for dev mode.
        firestore_database: Firestore database ID.
        noor_log_level: Logging level.
        noor_browser_headless: Run browser in headless mode.
        noor_browser_channel: System browser channel (msedge/chrome).
        noor_cdp_endpoint: CDP WebSocket URL for external browser.
        noor_host: Server bind host.
        noor_port: Server bind port.
        noor_streaming_mode: Enable Gemini Live API streaming.
    """

    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: str = "TRUE"
    google_api_key: str = ""
    firestore_database: str = "(default)"
    noor_log_level: str = "INFO"
    noor_browser_headless: bool = True
    noor_browser_channel: str = ""
    noor_cdp_endpoint: str = ""
    noor_host: str = "0.0.0.0"
    noor_port: int = Field(default=8080)
    noor_streaming_mode: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
