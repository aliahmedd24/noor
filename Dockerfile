# ── Stage 1: Builder ──
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r noor && useradd -r -g noor -m noor

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Install Playwright Chromium with ALL system dependencies.
# This is the ONLY place Chromium gets installed.
# On Windows dev machines, use NOOR_BROWSER_CHANNEL=msedge instead.
RUN playwright install chromium --with-deps

# Copy application code
COPY noor_agent/ ./noor_agent/
COPY server/ ./server/
COPY client/ ./client/

# Change ownership to non-root user
RUN chown -R noor:noor /app

# Production defaults
ENV GOOGLE_GENAI_USE_VERTEXAI=TRUE \
    NOOR_BROWSER_HEADLESS=true \
    NOOR_SESSION_BACKEND=vertex

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

USER noor

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
