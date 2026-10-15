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

# Everything goes to the web service; Hosting itself answers only its reserved /__/ paths
# (the sign-in handler). Page HTML is never cached: the app sends it as private, no-store.
resource "google_firebase_hosting_version" "web" {
  provider = google-beta
  site_id  = google_firebase_hosting_site.web.site_id

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
  version_name = google_firebase_hosting_version.web.name
  # Bump when Hosting needs a fresh release (a release is immutable). (2): the first one
  # predates the custom domains.
  message = "Cloud Run web service, from Terraform (2)"
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
