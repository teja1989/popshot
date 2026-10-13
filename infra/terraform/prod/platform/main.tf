# Everything except the Cloud Run services: network, database, identities, jobs, Firebase.
# Applied first on each deploy, so the database bootstrap and migrations run with the new
# image before any new API code serves traffic.

data "google_project" "this" {}

locals {
  project_number = data.google_project.this.number
  # Cloud Run's deterministic URL for the "web" service (see services stack).
  web_host = "web-${local.project_number}.${var.region}.run.app"
  web_url  = "https://${local.web_host}"

  db_name           = "popshot"
  sql_ca_mount_path = "/secrets/sql-ca"
  sql_ca_file       = "${local.sql_ca_mount_path}/server-ca.pem"
  # Cloud SQL's IAM user name for a service account drops ".gserviceaccount.com".
  api_db_user      = trimsuffix(google_service_account.api.email, ".gserviceaccount.com")
  migrator_db_user = trimsuffix(google_service_account.migrate.email, ".gserviceaccount.com")
  jobs_db_user     = trimsuffix(google_service_account.tick.email, ".gserviceaccount.com")
  admin_db_user    = trimsuffix(google_service_account.admin.email, ".gserviceaccount.com")
  db_ip            = google_sql_database_instance.main.private_ip_address
  # verify-ca: the connection is encrypted and the server must present Cloud SQL's CA.
  ssl_params = "sslmode=verify-ca&sslrootcert=${urlencode(local.sql_ca_file)}"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",
    "apikeys.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudscheduler.googleapis.com",
    "compute.googleapis.com",
    "firebase.googleapis.com",
    "identitytoolkit.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "sqladmin.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ---------------------------------------------------------------- network

resource "google_compute_network" "main" {
  name                    = "popshot"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

# Cloud Run services and jobs attach here with Direct VPC egress.
resource "google_compute_subnetwork" "run" {
  name          = "run"
  network       = google_compute_network.main.id
  region        = var.region
  ip_cidr_range = "10.10.0.0/24"
  # Lets the web service reach the internal-only API's *.run.app address over the VPC.
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.1
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_global_address" "private_services" {
  name          = "google-private-services"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

# ---------------------------------------------------------------- identities

resource "google_service_account" "web" {
  account_id   = "run-web"
  display_name = "Cloud Run: web"
}

resource "google_service_account" "api" {
  account_id   = "run-api"
  display_name = "Cloud Run: api (database login: popshot_app)"
}

# The admin pages (popshot_api.admin_main): its own identity and database login, the only
# one in popshot_admin, so the API can't reach the admin functions or account lookups.
resource "google_service_account" "admin" {
  account_id   = "run-admin"
  display_name = "Cloud Run: admin-api (database login: popshot_app + popshot_admin)"
}

resource "google_service_account" "migrate" {
  account_id   = "job-migrate"
  display_name = "Cloud Run job: migrations (database login: popshot_owner)"
}

resource "google_service_account" "tick" {
  account_id   = "job-tick"
  display_name = "Cloud Run job: scheduled tasks (database login: popshot_jobs)"
}

# Only starts the tick job. Nothing else.
resource "google_service_account" "scheduler" {
  account_id   = "scheduler-tick"
  display_name = "Cloud Scheduler: starts the tick job"
}

resource "google_service_account" "db_admin" {
  account_id   = "job-db-admin"
  display_name = "Cloud Run job: database bootstrap (Cloud SQL admin)"
}

# gha-deploy may deploy as these accounts, and no others.
resource "google_service_account_iam_member" "deploy_act_as" {
  for_each = {
    web       = google_service_account.web.name
    api       = google_service_account.api.name
    admin     = google_service_account.admin.name
    migrate   = google_service_account.migrate.name
    db_admin  = google_service_account.db_admin.name
    tick      = google_service_account.tick.name
    scheduler = google_service_account.scheduler.name
  }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.deploy_service_account}"
}

resource "google_project_iam_member" "sql_client" {
  for_each = {
    api      = google_service_account.api.member
    admin    = google_service_account.admin.member
    migrate  = google_service_account.migrate.member
    db_admin = google_service_account.db_admin.member
    tick     = google_service_account.tick.member
  }
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = each.value
}

# IAM database login (ADR 0005).
resource "google_project_iam_member" "sql_instance_user" {
  for_each = {
    api     = google_service_account.api.member
    admin   = google_service_account.admin.member
    migrate = google_service_account.migrate.member
    tick    = google_service_account.tick.member
  }
  project = var.project_id
  role    = "roles/cloudsql.instanceUser"
  member  = each.value
}

# The admin pages look up a person's email from Identity Platform when an admin opens them
# (popshot_api.accounts); emails aren't stored in the database. Read-only, and only the
# admin service has it (it moved here from the API).
resource "google_project_iam_member" "admin_account_lookup" {
  project = var.project_id
  role    = "roles/firebaseauth.viewer"
  member  = google_service_account.admin.member
}

# When an account is deleted (migration 0023), the tick job deletes its Firebase sign-in,
# where the email lives. A custom role with that one permission: the job can't read,
# create or change sign-ins.
resource "google_project_iam_custom_role" "delete_sign_ins" {
  project     = var.project_id
  role_id     = "popshotDeleteSignIns"
  title       = "Popshot: delete sign-ins"
  description = "Deletes Firebase Authentication users, nothing else. For the tick job."
  permissions = ["firebaseauth.users.delete"]
}

resource "google_project_iam_member" "tick_delete_sign_ins" {
  project = var.project_id
  role    = google_project_iam_custom_role.delete_sign_ins.id
  member  = google_service_account.tick.member
}

# Recaps can be written by Gemini on Vertex AI (popshot_api.ai_recap), as the API's own
# service account. It only runs when the services stack turns POPSHOT_RECAP_AI on.
resource "google_project_iam_member" "api_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = google_service_account.api.member

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------- database

resource "google_sql_database_instance" "main" {
  name                     = "popshot-pg"
  database_version         = "POSTGRES_16"
  region                   = var.region
  deletion_protection      = true
  root_password_wo         = ephemeral.random_password.db_admin.result
  root_password_wo_version = var.admin_password_version

  settings {
    edition                     = "ENTERPRISE"
    tier                        = "db-f1-micro"
    availability_type           = "ZONAL"
    disk_type                   = "PD_SSD"
    disk_size                   = 10
    disk_autoresize             = true
    deletion_protection_enabled = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "07:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 7
      }
    }

    maintenance_window {
      day          = 7
      hour         = 8
      update_track = "stable"
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }
    database_flags {
      name  = "log_connections"
      value = "on"
    }
    database_flags {
      name  = "log_disconnections"
      value = "on"
    }
    database_flags {
      name  = "log_lock_waits"
      value = "on"
    }
    database_flags {
      name  = "log_temp_files"
      value = "0"
    }
    database_flags {
      name  = "log_min_error_statement"
      value = "error"
    }
  }

  depends_on = [google_service_networking_connection.private_services]
}

resource "google_sql_database" "popshot" {
  name     = local.db_name
  instance = google_sql_database_instance.main.name
}

# The built-in admin (postgres). Its password is generated per rotation and written only to
# Cloud SQL (root_password_wo on the instance) and Secret Manager (secret_data_wo): it is
# never in state, plans or logs.
ephemeral "random_password" "db_admin" {
  length  = 40
  special = false
}

resource "google_sql_user" "api" {
  name     = local.api_db_user
  instance = google_sql_database_instance.main.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

resource "google_sql_user" "migrate" {
  name     = local.migrator_db_user
  instance = google_sql_database_instance.main.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

resource "google_sql_user" "admin" {
  name     = local.admin_db_user
  instance = google_sql_database_instance.main.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

resource "google_sql_user" "tick" {
  name     = local.jobs_db_user
  instance = google_sql_database_instance.main.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

# ---------------------------------------------------------------- secrets

resource "google_secret_manager_secret" "db_admin_url" {
  secret_id = "db-admin-url"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "db_admin_url" {
  secret = google_secret_manager_secret.db_admin_url.id
  secret_data_wo = format(
    "postgresql://postgres:%s@%s/postgres?%s",
    ephemeral.random_password.db_admin.result,
    local.db_ip,
    local.ssl_params,
  )
  secret_data_wo_version = var.admin_password_version
}

# Cloud SQL's server CA certificate. Public, but delivered as a file for sslrootcert.
resource "google_secret_manager_secret" "sql_ca" {
  secret_id = "sql-server-ca"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "sql_ca" {
  secret      = google_secret_manager_secret.sql_ca.id
  secret_data = google_sql_database_instance.main.server_ca_cert[0].cert
}

resource "google_secret_manager_secret_iam_member" "sql_ca" {
  for_each = {
    api      = google_service_account.api.member
    admin    = google_service_account.admin.member
    migrate  = google_service_account.migrate.member
    db_admin = google_service_account.db_admin.member
    tick     = google_service_account.tick.member
  }
  secret_id = google_secret_manager_secret.sql_ca.id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value
}

# The Web Push (VAPID) signing key. Generated here so a deploy needs no manual step; it's
# in this stack's state, which lives in the private, versioned state bucket like the other
# generated secrets. Only the API can read it. To rotate: terraform taint the key (people
# then need to turn notifications on again, since devices are tied to the public key).
resource "tls_private_key" "push_vapid" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "google_secret_manager_secret" "push_vapid" {
  secret_id = "push-vapid-key"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "push_vapid" {
  secret      = google_secret_manager_secret.push_vapid.id
  secret_data = tls_private_key.push_vapid.private_key_pem
}

resource "google_secret_manager_secret_iam_member" "push_vapid" {
  for_each = {
    api  = google_service_account.api.member
    tick = google_service_account.tick.member
  }
  secret_id = google_secret_manager_secret.push_vapid.id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value
}

# Only the bootstrap job can read the admin URL. The API never can.
resource "google_secret_manager_secret_iam_member" "db_admin_url" {
  secret_id = google_secret_manager_secret.db_admin_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.db_admin.member
}

# ---------------------------------------------------------------- jobs

locals {
  job_vpc = {
    network    = google_compute_network.main.id
    subnetwork = google_compute_subnetwork.run.id
  }
}

# Idempotent: group roles, memberships, database ownership (ADR 0005).
resource "google_cloud_run_v2_job" "db_bootstrap" {
  name                = "db-bootstrap"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.db_admin.email
      max_retries     = 0
      timeout         = "300s"

      vpc_access {
        network_interfaces {
          network    = local.job_vpc.network
          subnetwork = local.job_vpc.subnetwork
        }
        egress = "PRIVATE_RANGES_ONLY"
      }

      containers {
        image   = var.api_image
        command = ["python", "-m", "popshot_api.ops.bootstrap_db"]
        args = [
          "--migrator", local.migrator_db_user,
          "--api", local.api_db_user,
          "--jobs", local.jobs_db_user,
          "--admin", local.admin_db_user,
          "--database", local.db_name,
        ]

        env {
          name = "POPSHOT_BOOTSTRAP_ADMIN_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.db_admin_url.secret_id
              version = "latest"
            }
          }
        }

        volume_mounts {
          name       = "sql-ca"
          mount_path = local.sql_ca_mount_path
        }
      }

      volumes {
        name = "sql-ca"
        secret {
          secret = google_secret_manager_secret.sql_ca.secret_id
          items {
            version = "latest"
            path    = "server-ca.pem"
          }
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_version.db_admin_url,
    google_secret_manager_secret_version.sql_ca,
    google_secret_manager_secret_iam_member.db_admin_url,
    google_secret_manager_secret_iam_member.sql_ca,
    google_sql_user.api,
    google_sql_user.admin,
    google_sql_user.migrate,
    google_sql_user.tick,
  ]
}

resource "google_cloud_run_v2_job" "migrate" {
  name                = "migrate"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.migrate.email
      max_retries     = 0
      timeout         = "600s"

      vpc_access {
        network_interfaces {
          network    = local.job_vpc.network
          subnetwork = local.job_vpc.subnetwork
        }
        egress = "PRIVATE_RANGES_ONLY"
      }

      containers {
        image   = var.api_image
        command = ["alembic", "upgrade", "head"]

        env {
          name = "POPSHOT_MIGRATION_DATABASE_URL"
          value = format(
            "postgresql+psycopg://%s@%s/%s?%s",
            urlencode(local.migrator_db_user), local.db_ip, local.db_name, local.ssl_params,
          )
        }
        env {
          name  = "POPSHOT_DATABASE_IAM_AUTH"
          value = "true"
        }

        volume_mounts {
          name       = "sql-ca"
          mount_path = local.sql_ca_mount_path
        }
      }

      volumes {
        name = "sql-ca"
        secret {
          secret = google_secret_manager_secret.sql_ca.secret_id
          items {
            version = "latest"
            path    = "server-ca.pem"
          }
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.sql_ca,
    google_project_iam_member.sql_instance_user,
    google_sql_user.migrate,
  ]
}

# ---------------------------------------------------------------- scheduled job

# Every 15 minutes: play-night reminders and purging deleted groups (popshot_api.ops.tick).
# Logs in as popshot_jobs, which can only call the functions migration 0008 grants it.
resource "google_cloud_run_v2_job" "tick" {
  name                = "tick"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.tick.email
      # The next run is 15 minutes away; a retry could only send reminders late.
      max_retries = 0
      timeout     = "300s"

      vpc_access {
        network_interfaces {
          network    = local.job_vpc.network
          subnetwork = local.job_vpc.subnetwork
        }
        # The database over the VPC; push services over the internet.
        egress = "PRIVATE_RANGES_ONLY"
      }

      containers {
        image   = var.api_image
        command = ["python", "-m", "popshot_api.ops.tick"]

        env {
          name = "POPSHOT_JOBS_DATABASE_URL"
          value = format(
            "postgresql+psycopg://%s@%s/%s?%s",
            urlencode(local.jobs_db_user), local.db_ip, local.db_name, local.ssl_params,
          )
        }
        env {
          name  = "POPSHOT_DATABASE_IAM_AUTH"
          value = "true"
        }
        env {
          name = "POPSHOT_PUSH_VAPID_PRIVATE_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.push_vapid.secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "POPSHOT_PUSH_SUBJECT"
          value = local.web_url
        }
        env {
          name  = "POPSHOT_FIREBASE_PROJECT_ID"
          value = var.project_id
        }

        volume_mounts {
          name       = "sql-ca"
          mount_path = local.sql_ca_mount_path
        }
      }

      volumes {
        name = "sql-ca"
        secret {
          secret = google_secret_manager_secret.sql_ca.secret_id
          items {
            version = "latest"
            path    = "server-ca.pem"
          }
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.sql_ca,
    google_secret_manager_secret_iam_member.push_vapid,
    google_secret_manager_secret_version.push_vapid,
    google_project_iam_member.sql_instance_user,
    google_sql_user.tick,
    google_project_iam_member.tick_delete_sign_ins,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_tick" {
  name     = google_cloud_run_v2_job.tick.name
  location = var.region
  role     = "roles/run.invoker"
  member   = google_service_account.scheduler.member
}

resource "google_cloud_scheduler_job" "tick" {
  name      = "tick"
  region    = var.region
  schedule  = "*/15 * * * *"
  time_zone = "Etc/UTC"
  # A missed run is fine: the next one catches up.
  attempt_deadline = "60s"
  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.tick.name}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.apis,
    google_cloud_run_v2_job_iam_member.scheduler_runs_tick,
  ]
}
