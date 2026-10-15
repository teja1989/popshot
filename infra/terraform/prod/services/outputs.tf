# The app's address: our domain, through Firebase Hosting.
output "web_url" {
  value = local.platform.web_url
}

# Cloud Run's deterministic URL, not .uri (the older hash-style one). Pages opened there
# redirect to web_url.
output "run_url" {
  value = local.platform.run_url
}

output "api_url" {
  description = "Internal only; reachable from the web service through the VPC."
  value       = google_cloud_run_v2_service.api.uri
}

output "admin_api_url" {
  description = "Internal only; reachable from the web service through the VPC."
  value       = google_cloud_run_v2_service.admin_api.uri
}
