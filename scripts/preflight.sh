#!/bin/bash
# Pre-flight validation for Noor deployment.
# Checks environment variables, GCP APIs, and Docker availability.
set -euo pipefail

ERRORS=0

echo "=== Noor Pre-flight Checks ==="

# ── Required environment variables ──
check_env() {
    local var_name="$1"
    local required="${2:-true}"
    if [ -z "${!var_name:-}" ]; then
        if [ "$required" = "true" ]; then
            echo "[FAIL] $var_name is not set"
            ERRORS=$((ERRORS + 1))
        else
            echo "[WARN] $var_name is not set (optional)"
        fi
    else
        echo "[ OK ] $var_name is set"
    fi
}

echo ""
echo "--- Environment Variables ---"
check_env GOOGLE_CLOUD_PROJECT true
check_env GOOGLE_CLOUD_LOCATION false
check_env GOOGLE_GENAI_USE_VERTEXAI false

# ── CLI tools ──
echo ""
echo "--- CLI Tools ---"

check_tool() {
    if command -v "$1" &>/dev/null; then
        echo "[ OK ] $1 found: $(command -v "$1")"
    else
        echo "[FAIL] $1 not found"
        ERRORS=$((ERRORS + 1))
    fi
}

check_tool gcloud
check_tool docker
check_tool adk

# ── GCP Authentication ──
echo ""
echo "--- GCP Authentication ---"
if gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1 | grep -q .; then
    ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
    echo "[ OK ] Authenticated as: $ACCOUNT"
else
    echo "[FAIL] No active GCP authentication. Run: gcloud auth login"
    ERRORS=$((ERRORS + 1))
fi

# ── GCP APIs ──
echo ""
echo "--- GCP APIs ---"
PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
if [ -n "$PROJECT" ]; then
    check_api() {
        if gcloud services list --project="$PROJECT" --enabled --filter="name:$1" --format="value(name)" 2>/dev/null | grep -q "$1"; then
            echo "[ OK ] $1 enabled"
        else
            echo "[FAIL] $1 not enabled. Run: gcloud services enable $1 --project=$PROJECT"
            ERRORS=$((ERRORS + 1))
        fi
    }

    check_api run.googleapis.com
    check_api aiplatform.googleapis.com
    check_api artifactregistry.googleapis.com
else
    echo "[SKIP] No project set, skipping API checks"
fi

# ── Docker ──
echo ""
echo "--- Docker ---"
if docker info &>/dev/null; then
    echo "[ OK ] Docker daemon is running"
else
    echo "[FAIL] Docker daemon is not running"
    ERRORS=$((ERRORS + 1))
fi

# ── Summary ──
echo ""
if [ $ERRORS -gt 0 ]; then
    echo "=== Pre-flight FAILED: $ERRORS error(s) ==="
    exit 1
else
    echo "=== Pre-flight PASSED ==="
fi
