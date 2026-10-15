# Firebase Authentication (Identity Platform) for Google sign-in.
#
# Not managed here: the Google sign-in provider itself. Enabling it creates an OAuth client
# whose secret would otherwise sit in Terraform state, so it's a one-time console step
# (see infra/terraform/prod/README.md).

resource "google_firebase_project" "this" {
  provider   = google-beta
  project    = var.project_id
  depends_on = [google_project_service.apis]
}

# The browser key the web app ships. It can only call the two sign-in APIs, and only from
# the web app's addresses: our domain, where the sign-in pages (/__/auth) also run, and the
# run.app address while we switch over. The firebaseapp.com entry is the old auth domain.
resource "google_apikeys_key" "web" {
  name         = "popshot-web"
  display_name = "Popshot web (sign-in only)"

  restrictions {
    browser_key_restrictions {
      allowed_referrers = [
        "${local.web_url}/*",
        "${local.run_url}/*",
        "https://${var.project_id}.firebaseapp.com/*",
      ]
    }
    api_targets {
      service = "identitytoolkit.googleapis.com"
    }
    api_targets {
      service = "securetoken.googleapis.com"
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_firebase_web_app" "web" {
  provider     = google-beta
  project      = var.project_id
  display_name = "Popshot web"
  api_key_id   = google_apikeys_key.web.uid
  depends_on   = [google_firebase_project.this]
}

data "google_firebase_web_app_config" "web" {
  provider   = google-beta
  project    = var.project_id
  web_app_id = google_firebase_web_app.web.app_id
}

resource "google_identity_platform_config" "this" {
  project                    = var.project_id
  autodelete_anonymous_users = true

  # Where sign-in may complete. Firebase's own domains host the sign-in handler.
  authorized_domains = [
    "${var.project_id}.firebaseapp.com",
    "${var.project_id}.web.app",
    # Our domain, through Firebase Hosting (hosting.tf); www only redirects, so it isn't here.
    local.web_host,
    # The direct Cloud Run address, while we switch over.
    local.run_host,
  ]

  sign_in {
    allow_duplicate_emails = false

    email {
      enabled           = false
      password_required = false
    }
    phone_number {
      enabled = false
    }
    anonymous {
      enabled = false
    }
  }

  depends_on = [google_firebase_project.this]
}
