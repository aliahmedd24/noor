"""Custom exception classes for Noor."""

from __future__ import annotations


class NoorError(Exception):
    """Base exception for all Noor errors."""


class BrowserError(NoorError):
    """Raised when a browser operation fails."""


class BrowserLaunchError(BrowserError):
    """Raised when the browser cannot be launched with any strategy."""


class VisionError(NoorError):
    """Raised when Gemini vision analysis fails."""


class NavigationError(NoorError):
    """Raised when a browser navigation action fails."""


class StorageError(NoorError):
    """Raised when a Firestore operation fails."""


class VoiceStreamError(NoorError):
    """Raised when the voice streaming pipeline encounters an error."""
