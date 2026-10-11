# The two Cloud Run services. Applied after the platform stack and after migrations ran.

data "terraform_remote_state" "platform" {
  backend = "gcs"
  config = {
    bucket = var.state_bucket
    prefix = "prod/platform"
  }
}

locals {
  platform = data.terraform_remote_state.platform.outputs
}

# ---------------------------------------------------------------- api (internal only)

resource "google_cloud_run_v2_service" "api" {
  name                = "api"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = false

  template {
    service_account                  = local.platform.api_service_account
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "30s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    vpc_access {
      network_interfaces {
        network    = local.platform.network
        subnetwork = local.platform.subnetwork
      }
      # Cloud SQL over the VPC; Google's sign-in keys over the internet.
      egress = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.api_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "POPSHOT_ENVIRONMENT"
        value = "prod"
      }
      env {
        name  = "POPSHOT_FIREBASE_PROJECT_ID"
        value = local.platform.firebase.project_id
      }
      env {
        name  = "POPSHOT_DATABASE_URL"
        value = local.platform.api_database_url
      }
      env {
        name  = "POPSHOT_DATABASE_IAM_AUTH"
        value = "true"
      }
      env {
        name = "POPSHOT_PUSH_VAPID_PRIVATE_KEY"
        value_source {
          secret_key_ref {
            secret  = local.platform.push_vapid_secret
            version = "latest"
          }
        }
      }
      env {
        # Sent to push services as who to contact about our traffic.
        name  = "POPSHOT_PUSH_SUBJECT"
        value = local.platform.web_url
      }

      volume_mounts {
        name       = "sql-ca"
        mount_path = local.platform.sql_ca_mount_path
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds    = 3
        failure_threshold = 10
      }
    }

    volumes {
      name = "sql-ca"
      secret {
        secret = local.platform.sql_ca_secret
        items {
          version = "latest"
          path    = "server-ca.pem"
        }
      }
    }
  }
}

# Only the web service's identity may call the API (ARCHITECTURE: trust boundary 2).
resource "google_cloud_run_v2_service_iam_member" "api_invoker" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${local.platform.web_service_account}"
}

# ---------------------------------------------------------------- web (public)

resource "google_cloud_run_v2_service" "web" {
  # The name fixes the URL (web-<project number>.<region>.run.app) that the platform stack
  # already allowed for sign-in and the API key.
  name                = "web"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = local.platform.web_service_account
    execution_environment            = "EXECUTION_ENVIRONMENT_GEN2"
    timeout                          = "30s"
    max_instance_request_concurrency = 80

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    vpc_access {
      network_interfaces {
        network    = local.platform.network
        subnetwork = local.platform.subnetwork
      }
      # All traffic through the VPC: the only way to reach the internal-only API.
      egress = "ALL_TRAFFIC"
    }

    containers {
      image = var.web_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "API_BASE_URL"
        value = google_cloud_run_v2_service.api.uri
      }
      env {
        name  = "API_AUDIENCE"
        value = google_cloud_run_v2_service.api.uri
      }
      env {
        name  = "FIREBASE_API_KEY"
        value = local.platform.firebase.api_key
      }
      env {
        name  = "FIREBASE_AUTH_DOMAIN"
        value = local.platform.firebase.auth_domain
      }
      env {
        name  = "FIREBASE_PROJECT_ID"
        value = local.platform.firebase.project_id
      }
      env {
        name  = "FIREBASE_APP_ID"
        value = local.platform.firebase.app_id
      }

      startup_probe {
        http_get {
          path = "/icons/192"
        }
        period_seconds    = 3
        failure_threshold = 10
      }
    }
  }
}

# The web app is the public front door.
resource "google_cloud_run_v2_service_iam_member" "web_public" {
  name     = google_cloud_run_v2_service.web.name
  location = google_cloud_run_v2_service.web.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
