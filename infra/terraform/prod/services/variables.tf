variable "project_id" {
  description = "Google Cloud project ID."
  type        = string
}

variable "region" {
  type    = string
  default = "us-east4"
}

variable "state_bucket" {
  description = "Terraform state bucket, to read the platform stack's outputs."
  type        = string
}

variable "api_image" {
  description = "API image by digest."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.api_image))
    error_message = "Pass the API image by digest, not by tag."
  }
}

variable "web_image" {
  description = "Web image by digest."
  type        = string
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.web_image))
    error_message = "Pass the web image by digest, not by tag."
  }
}

variable "admin_emails" {
  description = "Who can open the admin page: comma-separated Google account emails. Empty: nobody. From the POPSHOT_ADMIN_EMAILS GitHub variable."
  type        = string
  default     = ""
}

variable "recap_ai" {
  description = "Whether Gemini writes recap words (popshot_api.ai_recap): \"true\" or anything else for off. From the POPSHOT_RECAP_AI GitHub variable."
  type        = string
  default     = ""
}
