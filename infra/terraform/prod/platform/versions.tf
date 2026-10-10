terraform {
  required_version = "~> 1.16.4"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.4.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "8.4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.9.1"
    }
  }

  # terraform init -backend-config="bucket=<project>-tfstate"
  backend "gcs" {
    prefix = "prod/platform"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
