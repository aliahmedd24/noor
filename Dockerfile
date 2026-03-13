FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium with ALL system dependencies.
# This is the ONLY place Chromium gets installed.
# On Windows dev machines, use NOOR_BROWSER_CHANNEL=msedge instead.
RUN playwright install chromium --with-deps

# Copy application code
COPY src/ ./src/
COPY client/ ./client/

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
