#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run pre-flight checks
echo "=== Running pre-flight checks ==="
bash "$SCRIPT_DIR/preflight.sh" || { echo "Pre-flight failed. Fix errors above."; exit 1; }
echo ""

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${NOOR_SERVICE_NAME:-noor-agent}"

echo "=== Deploying Noor via ADK CLI ==="
adk deploy cloud_run \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --service_name="${SERVICE_NAME}" \
    --app_name=noor \
    --trace_to_cloud \
    noor_agent

ADK_EXIT=$?

# Fallback: if ADK deploy fails (e.g. Playwright deps), use gcloud with custom Dockerfile
if [ $ADK_EXIT -ne 0 ]; then
    echo "=== ADK deploy failed, falling back to gcloud run deploy ==="
    gcloud run deploy "${SERVICE_NAME}" \
        --source=. \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --allow-unauthenticated \
        --memory=2Gi \
        --cpu=2 \
        --min-instances=0 \
        --max-instances=5 \
        --concurrency=10 \
        --session-affinity \
        --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE,NOOR_BROWSER_HEADLESS=true"
fi

echo "=== Deployment complete ==="
echo "Service URL:"
gcloud run services describe "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format="value(status.url)"
