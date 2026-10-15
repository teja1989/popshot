# Firebase Hosting in front of the Cloud Run "web" service, on our own domain.
#
#   browser ─▶ popshotpb.com (Cloudflare DNS, not proxied) ─▶ Firebase Hosting
#             (Google certificate, CDN, serves /__/auth/* for sign-in) ─▶ Cloud Run "web"
#
# DNS lives at Cloudflare (Cloudflare Registrar allows only its own DNS) and is added by
# hand from the dns_records output, so no Cloudflare token sits in CI. Until those records
# exist the domains wait in Firebase; nothing here waits on DNS.
#
# A site of its own rather than the project's default one, so Terraform creates it instead
# of adopting something Firebase may or may not have made already.

locals {
  hosting_site_id = "${substr(var.project_id, 0, 26)}-web"
  www_domain      = "www.${var.site_domain}"
}

resource "google_firebase_hosting_site" "web" {
  provider = google-beta
  project  = var.project_id
  site_id  = local.hosting_site_id
  # The web app whose config the sign-in pages (/__/auth, /__/firebase/init.json) serve.
  app_id     = google_firebase_web_app.web.app_id
  depends_on = [google_firebase_project.this, google_project_service.apis]

  # Replacing the site would drop the connected domains and their certificates: a plan that
  # wants to fails instead.
  lifecycle {
    prevent_destroy = true
  }
}

# Bump to publish Hosting afresh: a new version, and a release of it. Firebase won't
# re-release the version that's already live, so the version itself has to be new.
# 2: the first release predates the custom domains.
resource "terraform_data" "hosting_revision" {
  input = 2
}

# The first version, live since domain step 1: forgotten, never deleted (deleting the live
# version would take the site down). Its successor below replaces it in Hosting.
removed {
  from = google_firebase_hosting_version.web

  lifecycle {
    destroy = false
  }
}

# Everything goes to the web service; Hosting itself answers only its reserved /__/ paths
# (the sign-in handler). Page HTML is never cached: the app sends it as private, no-store.
resource "google_firebase_hosting_version" "web_v2" {
  provider = google-beta
  site_id  = google_firebase_hosting_site.web.site_id

  lifecycle {
    # A bump makes a new version; the old one goes only after the new one is released.
    replace_triggered_by  = [terraform_data.hosting_revision]
    create_before_destroy = true
  }

  config {
    rewrites {
      glob = "**"
      run {
        service_id = "web"
        region     = var.region
      }
    }
  }
}

resource "google_firebase_hosting_release" "web" {
  provider     = google-beta
  site_id      = google_firebase_hosting_site.web.site_id
  version_name = google_firebase_hosting_version.web_v2.name
  message      = "Cloud Run web service, from Terraform (${terraform_data.hosting_revision.output})"
}

resource "google_firebase_hosting_custom_domain" "apex" {
  provider              = google-beta
  project               = var.project_id
  site_id               = google_firebase_hosting_site.web.site_id
  custom_domain         = var.site_domain
  wait_dns_verification = false

  lifecycle {
    prevent_destroy = true
  }
}

# www only redirects to the main address.
resource "google_firebase_hosting_custom_domain" "www" {
  provider              = google-beta
  project               = var.project_id
  site_id               = google_firebase_hosting_site.web.site_id
  custom_domain         = local.www_domain
  redirect_target       = google_firebase_hosting_custom_domain.apex.custom_domain
  wait_dns_verification = false

  lifecycle {
    prevent_destroy = true
  }
}
