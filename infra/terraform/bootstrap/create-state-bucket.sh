#!/usr/bin/env bash
# Creates the Terraform state bucket once, before the first `terraform init`.
# Terraform then adopts it (see the import block in main.tf).
set -euo pipefail

project="${1:?usage: create-state-bucket.sh <project-id> [region]}"
region="${2:-us-east4}"
bucket="${project}-tfstate"

gcloud services enable storage.googleapis.com --project "$project"
if gcloud storage buckets describe "gs://${bucket}" --project "$project" >/dev/null 2>&1; then
  echo "gs://${bucket} already exists."
else
  gcloud storage buckets create "gs://${bucket}" \
    --project "$project" \
    --location "$region" \
    --uniform-bucket-level-access \
    --public-access-prevention
fi
gcloud storage buckets update "gs://${bucket}" --versioning
echo "State bucket ready: gs://${bucket}"
