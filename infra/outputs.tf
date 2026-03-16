output "service_account_email" {
  value = google_service_account.noor.email
}

output "cloud_run_url" {
  value = google_cloud_run_v2_service.noor.uri
}

output "artifact_registry_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.noor.repository_id}"
}
