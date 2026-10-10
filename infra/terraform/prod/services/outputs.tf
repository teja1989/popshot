output "web_url" {
  value = google_cloud_run_v2_service.web.uri
}

output "api_url" {
  description = "Internal only; reachable from the web service through the VPC."
  value       = google_cloud_run_v2_service.api.uri
}
