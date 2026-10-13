# One-time setup, applied by a person with their own credentials. Everything after this
# runs from GitHub Actions through Workload Identity Federation, with no keys anywhere.

locals {
  state_bucket = "${var.project_id}-tfstate"

  # The deploy identity manages every resource in infra/terraform/prod, including IAM and
  # the project's custom roles (roleAdmin: the narrow "delete sign-ins" role for the tick
  # job, migration 0023).
  # It gets serviceAccountUser only on the runtime service accounts it deploys (granted in
  # the prod stack), not project-wide.
  # That makes it close to project owner, which is why only an approved job on main can
  # use it (see the GitHub environment rules in README.md).
  deploy_roles = [
    "roles/artifactregistry.admin",
    "roles/cloudscheduler.admin",
    "roles/cloudsql.admin",
    "roles/compute.networkAdmin",
    "roles/firebase.admin",
    "roles/iam.roleAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/identitytoolkit.admin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/run.admin",
    "roles/secretmanager.admin",
    "roles/servicenetworking.networksAdmin",
    "roles/serviceusage.apiKeysAdmin",
    "roles/serviceusage.serviceUsageAdmin",
  ]

  # Read-only, for plans shown before approval.
  plan_roles = [
    "roles/viewer",
    "roles/iam.securityReviewer",
  ]
}

resource "google_project_service" "bootstrap" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ---- Terraform state ----

import {
  to = google_storage_bucket.tfstate
  id = local.state_bucket
}

resource "google_storage_bucket" "tfstate" {
  name                        = local.state_bucket
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 30
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

# ---- Container images ----

resource "google_artifact_registry_repository" "images" {
  repository_id = "popshot"
  location      = var.region
  format        = "DOCKER"
  description   = "Popshot container images"

  docker_config {
    immutable_tags = true
  }

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 20
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.bootstrap]
}

# ---- GitHub Actions identity (no keys) ----

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.bootstrap]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "popshot"
  display_name                       = "teja1989/popshot"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"                = "assertion.sub"
    "attribute.repository_id"       = "assertion.repository_id"
    "attribute.environment"         = "assertion.environment"
    "attribute.ref"                 = "assertion.ref"
    "attribute.repository_owner_id" = "assertion.repository_owner_id"
  }

  # Only this repository, only its main branch. Pull requests (refs/pull/...) and forks
  # can't get a token at all.
  attribute_condition = join(" && ", [
    "assertion.repository_id == '${var.github_repository_id}'",
    "assertion.repository_owner_id == '${var.github_owner_id}'",
    "assertion.ref == 'refs/heads/main'",
  ])
}

locals {
  github_environment = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.environment"
}

resource "google_service_account" "plan" {
  account_id   = "gha-plan"
  display_name = "GitHub Actions: terraform plan (read-only)"
}

resource "google_service_account" "build" {
  account_id   = "gha-build"
  display_name = "GitHub Actions: build and push images"
}

resource "google_service_account" "deploy" {
  account_id   = "gha-deploy"
  display_name = "GitHub Actions: apply and deploy (approved jobs only)"
}

# Which GitHub environment may use which identity. The prod environment requires approval.
resource "google_service_account_iam_member" "plan_wif" {
  service_account_id = google_service_account.plan.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "${local.github_environment}/prod-plan"
}

resource "google_service_account_iam_member" "build_wif" {
  service_account_id = google_service_account.build.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "${local.github_environment}/prod-plan"
}

resource "google_service_account_iam_member" "deploy_wif" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "${local.github_environment}/prod"
}

resource "google_project_iam_member" "plan" {
  for_each = toset(local.plan_roles)
  project  = var.project_id
  role     = each.key
  member   = google_service_account.plan.member
}

resource "google_project_iam_member" "deploy" {
  for_each = toset(local.deploy_roles)
  project  = var.project_id
  role     = each.key
  member   = google_service_account.deploy.member
}

# Plans read state without taking the lock; only the deploy identity writes state.
resource "google_storage_bucket_iam_member" "plan_state" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectViewer"
  member = google_service_account.plan.member
}

resource "google_storage_bucket_iam_member" "deploy_state" {
  bucket = google_storage_bucket.tfstate.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.deploy.member
}

resource "google_artifact_registry_repository_iam_member" "build_push" {
  repository = google_artifact_registry_repository.images.name
  location   = google_artifact_registry_repository.images.location
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.build.member
}
