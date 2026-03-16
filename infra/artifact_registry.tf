resource "google_artifact_registry_repository" "noor" {
  location      = var.region
  repository_id = "noor"
  description   = "Docker images for Noor agent"
  format        = "DOCKER"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}
