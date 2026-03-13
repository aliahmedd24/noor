"""Noor FastAPI entrypoint — WebSocket server and REST health checks."""

from __future__ import annotations

import sys

if sys.platform == "win32" and sys.version_info < (3, 14):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.utils.logging import setup_logging

setup_logging()

app = FastAPI(
    title="Noor",
    description="AI-powered web navigator for visually impaired users",
    version="0.1.0",
)

app.mount("/client", StaticFiles(directory="client"), name="client")


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for Cloud Run."""
    return {"status": "healthy", "version": "0.1.0"}
