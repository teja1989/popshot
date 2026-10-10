# Bootstrap (run once, by a person)

Creates what GitHub Actions needs to manage everything else without any keys:

| Resource | Why |
|---|---|
| State bucket `<project>-tfstate` | Terraform state: versioned, no public access |
| Artifact Registry repo `popshot` | Container images. Tags can't be overwritten; old images are cleaned up |
| Workload Identity pool `github` | Lets GitHub Actions sign in to Google Cloud with short-lived tokens. Only `teja1989/popshot` (by numeric ID) on `main` is accepted |
| `gha-plan` service account | Read-only. Runs `terraform plan` before you approve |
| `gha-build` service account | Pushes images to the `popshot` repo, nothing else |
| `gha-deploy` service account | Applies Terraform and deploys. Only usable by a job in the `prod` environment, which needs your approval |

## Prerequisites

- `gcloud` signed in as a project owner: `gcloud auth login && gcloud auth application-default login`
- Terraform 1.16.4

## Steps

```sh
cd infra/terraform/bootstrap
./create-state-bucket.sh <project-id> us-east4
cp terraform.tfvars.example terraform.tfvars        # set project_id; the file is gitignored
terraform init -backend-config="bucket=<project-id>-tfstate"
terraform plan                                       # review: about 30 resources, 1 import
terraform apply
terraform output
```

## Then, in GitHub (repository settings; only you can do this)

1. **Settings → Environments → New environment `prod-plan`**
   - Deployment branches: *Selected branches* → `main`
2. **New environment `prod`**
   - Required reviewers: yourself
   - Deployment branches: *Selected branches* → `main`
3. On **both** environments, add these **variables** (not secrets; none of them are sensitive):

   | Variable | Value |
   |---|---|
   | `GCP_PROJECT_ID` | your project ID |
   | `GCP_REGION` | `us-east4` |
   | `WIF_PROVIDER` | output `workload_identity_provider` |
   | `GCP_PLAN_SA` | output `plan_service_account` |
   | `GCP_BUILD_SA` | output `build_service_account` |
   | `GCP_DEPLOY_SA` | output `deploy_service_account` |
   | `TF_STATE_BUCKET` | output `state_bucket` |
   | `IMAGE_REPOSITORY` | output `image_repository` |

The deploy workflow arrives in a later PR and uses these.

## Notes

- `gha-deploy` can change IAM in the project, because Terraform manages IAM. That makes it
  nearly as powerful as an owner, so it's locked to approved jobs on `main`.
- Plans run without taking the state lock (`-lock=false`), so `gha-plan` only needs to read state.
- To undo: `terraform destroy` won't delete the state bucket (`prevent_destroy`); remove it
  by hand once nothing else needs it.
