# PHASE 5: GCP DEPLOYMENT & INFRASTRUCTURE

## Objective

Deploy Noor to Google Cloud Platform with production-grade infrastructure. This phase covers Cloud Run deployment, Firestore setup, Secret Manager integration, Cloud Logging, and Terraform IaC automation. This directly satisfies the hackathon requirements for "Proof of Google Cloud Deployment" and earns the **+0.2 bonus points for automated deployment**.

---

## 5.1 — GCP SERVICES MAP

| Service | Purpose | Why This Service |
|---------|---------|-----------------|
| **Cloud Run** | Host the FastAPI + ADK backend | Serverless containers, auto-scales to zero, WebSocket support |
| **Vertex AI** | Gemini model API access | Enterprise-grade, same API as dev but with service account auth |
| **Firestore** | User preferences, session history | Serverless NoSQL, free tier, real-time listeners |
| **Secret Manager** | API keys, credentials | Best practice for credential management on GCP |
| **Cloud Logging** | Structured log collection | Auto-integrated with Cloud Run, JSON logs from structlog |
| **Cloud Monitoring** | Health dashboards, alerting | Latency tracking, error rate monitoring |
| **Artifact Registry** | Docker image storage | Where Cloud Run pulls container images from |

---

## 5.2 — CLOUD RUN DEPLOYMENT

### Service Configuration

```yaml
# Cloud Run service specifications
service_name: noor-agent
region: us-central1
image: us-central1-docker.pkg.dev/${PROJECT_ID}/noor/noor-agent:latest

resources:
  cpu: 2
  memory: 2Gi    # Playwright + Chromium needs memory
  startup_cpu_boost: true

scaling:
  min_instances: 0
  max_instances: 5
  concurrency: 10  # Each WebSocket = 1 concurrent connection

environment_variables:
  GOOGLE_CLOUD_PROJECT: ${PROJECT_ID}
  GOOGLE_CLOUD_LOCATION: us-central1
  GOOGLE_GENAI_USE_VERTEXAI: "TRUE"
  FIRESTORE_DATABASE: "(default)"
  NOOR_LOG_LEVEL: "INFO"
  NOOR_BROWSER_HEADLESS: "true"
  NOOR_STREAMING_MODE: "true"
  NOOR_PORT: "8080"

# WebSocket support requires HTTP/2 and session affinity
session_affinity: true
ingress: all
```

### Dockerfile Adjustments for Cloud Run

The Dockerfile from Phase 0 is Cloud Run-ready. Key points:
- Expose port 8080 (Cloud Run default)
- Use `--no-sandbox` flag for Chromium (required in containers)
- Install all Playwright system dependencies

---

## 5.3 — FIRESTORE SCHEMA

### Collections

```
noor-db/
├── users/
│   └── {user_id}/
│       ├── preferences: {
│       │     voice_speed: "normal",      # slow, normal, fast
│       │     verbosity: "standard",      # brief, standard, detailed
│       │     auto_dismiss_cookies: true,
│       │     favorite_sites: ["bbc.com", "google.com"],
│       │     language: "en"
│       │   }
│       └── sessions/
│           └── {session_id}/
│               ├── created_at: timestamp
│               ├── last_active: timestamp
│               ├── conversation_summary: string
│               └── pages_visited: [string]
│
└── analytics/
    └── {date}/
        ├── total_sessions: number
        ├── pages_navigated: number
        └── avg_session_duration: number
```

### Firestore Client (`src/storage/firestore_client.py`)

```python
"""
Firestore client for Noor user data and session persistence.

Uses the async Firestore client for non-blocking operations.
Falls back to in-memory storage if Firestore is unavailable (dev mode).
"""
from google.cloud import firestore
from datetime import datetime


class NoorFirestore:
    """Firestore operations for Noor."""

    def __init__(self, project_id: str, database: str = "(default)"):
        self.db = firestore.AsyncClient(project=project_id, database=database)

    async def get_user_preferences(self, user_id: str) -> dict:
        """Get user preferences, returning defaults if not found."""

    async def save_user_preferences(self, user_id: str, preferences: dict) -> None:
        """Save/update user preferences."""

    async def log_session(self, user_id: str, session_id: str,
                          pages_visited: list[str], summary: str) -> None:
        """Log a completed session."""

    async def get_favorite_sites(self, user_id: str) -> list[str]:
        """Get user's frequently visited sites."""
```

### User Preference Tools (`src/tools/user_tools.py`)

```python
async def get_user_preference(preference_name: str) -> dict:
    """Get a user preference setting.

    Available preferences: voice_speed, verbosity, auto_dismiss_cookies, language.

    Args:
        preference_name: Name of the preference to retrieve.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - preference: The preference name
        - value: The preference value
    """


async def save_user_preference(preference_name: str, value: str) -> dict:
    """Save a user preference setting.

    Args:
        preference_name: Name of the preference (voice_speed, verbosity, etc.).
        value: New value for the preference.

    Returns:
        A dictionary with:
        - status: 'success' or 'error'
    """
```

---

## 5.4 — TERRAFORM INFRASTRUCTURE (`infra/`)

This earns the **+0.2 bonus points** for automated cloud deployment.

### `infra/main.tf`

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
```

### `infra/variables.tf`

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "noor-agent"
}
```

### `infra/cloud_run.tf`

```hcl
# Artifact Registry repository
resource "google_artifact_registry_repository" "noor" {
  repository_id = "noor"
  location      = var.region
  format        = "DOCKER"
  description   = "Container images for Noor agent"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# Cloud Run service
resource "google_cloud_run_v2_service" "noor" {
  name     = var.service_name
  location = var.region

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/noor/${var.service_name}:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "TRUE"
      }
      env {
        name  = "NOOR_BROWSER_HEADLESS"
        value = "true"
      }
      env {
        name  = "NOOR_STREAMING_MODE"
        value = "true"
      }
    }

    # Service account with Vertex AI and Firestore permissions
    service_account = google_service_account.noor.email

    # Session affinity for WebSocket connections
    session_affinity = true
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_artifact_registry_repository.noor,
  ]
}

# Service account for Cloud Run
resource "google_service_account" "noor" {
  account_id   = "noor-agent"
  display_name = "Noor Agent Service Account"
}

# IAM: Vertex AI User
resource "google_project_iam_member" "vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.noor.email}"
}

# IAM: Firestore User
resource "google_project_iam_member" "firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.noor.email}"
}

# IAM: Secret Manager Accessor
resource "google_project_iam_member" "secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.noor.email}"
}

# IAM: Logging Writer
resource "google_project_iam_member" "logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.noor.email}"
}

# Make the service publicly accessible (for hackathon demo)
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.noor.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
```

### `infra/firestore.tf`

```hcl
resource "google_firestore_database" "noor" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis["firestore.googleapis.com"]]
}
```

### `infra/outputs.tf`

```hcl
output "service_url" {
  description = "URL of the deployed Noor Cloud Run service"
  value       = google_cloud_run_v2_service.noor.uri
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.noor.email
}
```

---

## 5.5 — DEPLOYMENT SCRIPT (`scripts/deploy.sh`)

```bash
#!/bin/bash
# Noor — Build and deploy to Cloud Run
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="noor-agent"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/noor/${SERVICE_NAME}:latest"

echo "=== Building container image ==="
docker build -t "${IMAGE}" .

echo "=== Pushing to Artifact Registry ==="
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker push "${IMAGE}"

echo "=== Deploying to Cloud Run ==="
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 5 \
  --concurrency 10 \
  --session-affinity \
  --service-account "noor-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE,NOOR_BROWSER_HEADLESS=true,NOOR_STREAMING_MODE=true"

echo "=== Deployment complete ==="
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format "value(status.url)"
```

---

## 5.6 — GCP SETUP SCRIPT (`scripts/setup_gcp.sh`)

```bash
#!/bin/bash
# Noor — Initial GCP project setup
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"

echo "=== Enabling required APIs ==="
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project "${PROJECT_ID}"

echo "=== Creating Artifact Registry repository ==="
gcloud artifacts repositories create noor \
  --repository-format=docker \
  --location="${REGION}" \
  --description="Noor agent container images" \
  --project="${PROJECT_ID}" || true

echo "=== Creating service account ==="
gcloud iam service-accounts create noor-agent \
  --display-name="Noor Agent Service Account" \
  --project="${PROJECT_ID}" || true

SA_EMAIL="noor-agent@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== Granting IAM roles ==="
for ROLE in roles/aiplatform.user roles/datastore.user roles/secretmanager.secretAccessor roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None --quiet
done

echo "=== Creating Firestore database ==="
gcloud firestore databases create \
  --location="${REGION}" \
  --project="${PROJECT_ID}" || true

echo "=== Setup complete ==="
```

---

## 5.7 — STRUCTURED LOGGING (`src/utils/logging.py`)

```python
"""
Structured logging configuration for Cloud Logging compatibility.

Uses structlog with JSON output that Cloud Logging automatically parses
into searchable, structured log entries.
"""
import structlog
import logging
from src.config import settings


def setup_logging():
    """Configure structured logging for the application."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.noor_log_level.upper()),
    )
```

---

## 5.8 — IMPLEMENTATION ORDER

1. **`infra/main.tf`** + **`variables.tf`** + **`outputs.tf`** — Terraform foundation
2. **`infra/cloud_run.tf`** — Cloud Run + service account + IAM
3. **`infra/firestore.tf`** — Firestore database
4. **`scripts/setup_gcp.sh`** — Manual GCP setup script
5. **`scripts/deploy.sh`** — Build + deploy script
6. **`src/storage/firestore_client.py`** — Firestore operations
7. **`src/tools/user_tools.py`** — User preference ADK tools
8. **`src/utils/logging.py`** — Structured logging
9. **Test deployment** — Run Terraform plan, deploy to Cloud Run

---

## 5.9 — ACCEPTANCE CRITERIA

- [ ] `terraform plan` succeeds with no errors
- [ ] `terraform apply` provisions all GCP resources
- [ ] Cloud Run service is accessible via public URL
- [ ] WebSocket connection works through Cloud Run (session affinity)
- [ ] Vertex AI Gemini calls work with service account auth (no API key needed)
- [ ] Firestore reads/writes work from Cloud Run
- [ ] Cloud Logging shows structured JSON logs from the application
- [ ] `scripts/deploy.sh` builds and deploys in one command
- [ ] Service scales to zero when idle (cost management)

---

## 5.10 — GCP DEPLOYMENT PROOF (Hackathon Requirement)

The hackathon requires a separate recording proving GCP deployment. Create this proof:

1. **Screen record** showing:
   - GCP Console → Cloud Run → noor-agent service running
   - Logs tab showing live structured logs
   - The service URL resolving to Noor's UI
   - Vertex AI API calls in the logs

2. **Or** include in the repo a file `docs/gcp_deployment_proof.md` linking to:
   - The Cloud Run service URL
   - The Terraform configuration in `infra/`
   - The `deploy.sh` script showing automated deployment
