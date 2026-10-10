# Copy these into the GitHub environments' variables (see README.md). None are secrets.

output "workload_identity_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "plan_service_account" {
  value = google_service_account.plan.email
}

output "build_service_account" {
  value = google_service_account.build.email
}

output "deploy_service_account" {
  value = google_service_account.deploy.email
}

output "state_bucket" {
  value = google_storage_bucket.tfstate.name
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
