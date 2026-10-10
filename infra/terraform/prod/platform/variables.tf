variable "project_id" {
  description = "Google Cloud project ID (from the GCP_PROJECT_ID GitHub variable)."
  type        = string
}

variable "region" {
  description = "Region for everything regional."
  type        = string
  default     = "us-east4"
}

variable "api_image" {
  description = "API image by digest (repo@sha256:...). The bootstrap and migrate jobs run it."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
    error_message = "Pass the API image by digest, not by tag."
  }
}

variable "deploy_service_account" {
  description = "Email of gha-deploy. It may act as the runtime service accounts, and only those."
  type        = string
}

variable "admin_password_version" {
  description = "Bump to rotate the Cloud SQL admin password. The password never enters state."
  type        = number
  default     = 1
}

variable "billing_account" {
  description = "Billing account ID for the budget alert. Empty skips the budget."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Monthly budget; alerts go to billing admins at 50%, 90% and 100%."
  type        = number
  default     = 25
}
