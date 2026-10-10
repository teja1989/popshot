variable "project_id" {
  description = "Google Cloud project ID. Kept out of the repo: set it in terraform.tfvars (gitignored)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Not a valid Google Cloud project ID."
  }
}

variable "region" {
  description = "Region for the state bucket and the image repository."
  type        = string
  default     = "us-east4"
}

# GitHub identities are numeric so a renamed or re-created repository can't inherit access.
variable "github_repository_id" {
  description = "Numeric ID of teja1989/popshot (GET /repos/teja1989/popshot -> id)."
  type        = string
  default     = "1413208233"
}

variable "github_owner_id" {
  description = "Numeric ID of the repository owner (teja1989)."
  type        = string
  default     = "19315361"
}
