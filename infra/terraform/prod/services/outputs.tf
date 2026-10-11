# The deterministic URL, not .uri (the older hash-style one). Sign-in is only allowed from
# this one: the browser API key's referrer rule and Firebase's authorized domains name it.
output "web_url" {
  value = local.platform.web_url
}

output "api_url" {
  description = "Internal only; reachable from the web service through the VPC."
  value       = google_cloud_run_v2_service.api.uri
}
