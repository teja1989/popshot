terraform {
  required_version = "~> 1.16.4"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "8.4.0"
    }
  }

  # The bucket is created by create-state-bucket.sh before the first init, then adopted
  # below. Pass the bucket with: terraform init -backend-config="bucket=<project>-tfstate"
  backend "gcs" {
    prefix = "bootstrap"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
