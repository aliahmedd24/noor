# Service account for the Cloud Run service
resource "google_service_account" "noor" {
  account_id   = "noor-agent"
  display_name = "Noor Agent Service Account"
}

# Vertex AI User (for Gemini API calls)
resource "google_project_iam_member" "vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.noor.email}"
}

# Firestore User
resource "google_project_iam_member" "firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.noor.email}"
}

# Secret Manager Accessor
resource "google_project_iam_member" "secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.noor.email}"
}

# Cloud Logging Writer
resource "google_project_iam_member" "logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.noor.email}"
}

# Cloud Trace Agent (for --trace_to_cloud)
resource "google_project_iam_member" "trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.noor.email}"
}
