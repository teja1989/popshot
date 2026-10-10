terraform {
  required_version = "~> 1.16.4"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.4.0"
    }
  }

  # terraform init -backend-config="bucket=<project>-tfstate"
  backend "gcs" {
    prefix = "prod/services"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
