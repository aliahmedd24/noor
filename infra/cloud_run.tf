resource "google_cloud_run_v2_service" "noor" {
  name     = "noor-agent"
  location = var.region

  template {
    service_account = google_service_account.noor.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    timeout = "300s"

    session_affinity = true

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/noor/noor-agent:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
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
        name  = "NOOR_SESSION_BACKEND"
        value = "vertex"
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 6
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds = 30
      }
    }
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_artifact_registry_repository.noor,
  ]
}

# Allow unauthenticated access (demo/hackathon)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.noor.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
