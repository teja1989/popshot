# Read by the services stack (terraform_remote_state). Nothing here is secret: the Firebase
# web config is public by design, and the admin password never enters state.

output "web_url" {
  value = local.web_url
}

output "network" {
  value = google_compute_network.main.id
}

output "subnetwork" {
  value = google_compute_subnetwork.run.id
}

output "web_service_account" {
  value = google_service_account.web.email
}

output "api_service_account" {
  value = google_service_account.api.email
}

output "api_database_url" {
  value = format(
    "postgresql+psycopg://%s@%s/%s?%s",
    urlencode(local.api_db_user), local.db_ip, local.db_name, local.ssl_params,
  )
}

output "sql_ca_secret" {
  value = google_secret_manager_secret.sql_ca.secret_id
}

output "push_vapid_secret" {
  value = google_secret_manager_secret.push_vapid.secret_id
  # Reading the version makes sure it exists before the API that uses it is deployed.
  depends_on = [google_secret_manager_secret_version.push_vapid]
}

output "sql_ca_mount_path" {
  value = local.sql_ca_mount_path
}

output "firebase" {
  value = {
    api_key     = data.google_firebase_web_app_config.web.api_key
    auth_domain = data.google_firebase_web_app_config.web.auth_domain
    project_id  = var.project_id
    app_id      = google_firebase_web_app.web.app_id
  }
}

output "jobs" {
  value = {
    db_bootstrap = google_cloud_run_v2_job.db_bootstrap.name
    migrate      = google_cloud_run_v2_job.migrate.name
    tick         = google_cloud_run_v2_job.tick.name
  }
}
