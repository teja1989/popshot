#!/usr/bin/env bash
# Popshot: provision Google Cloud and GitHub, then start the first deploy. Run it from your
# Mac, from anywhere inside the repo:
#
#   ./infra/provision.sh <gcp-project-id> [region]
#
# Safe to re-run. It asks before every change. Nothing secret is printed or written to the repo.
# Works with macOS's built-in bash 3.2.
set -euo pipefail

REPO="teja1989/popshot"
TERRAFORM_VERSION="1.16.4"
# From HashiCorp's GPG-signed terraform_1.16.4_SHA256SUMS.
TERRAFORM_SHA256_darwin_arm64="42cfdf97ad722f79085fe2279b06d4b8680172de3534b22eeddd9a0fbbe7b8f1"
TERRAFORM_SHA256_darwin_amd64="2ee4b62064086e4b24b0d6cf2e61718fbaf0556feba990f708a5e32557554b3b"
TERRAFORM_SHA256_linux_amd64="dc94af0eef1147718ad7c8daea792ed199e3e0492eec180d0adafa2a65a879df"

PROJECT_ID="${1:-}"
REGION="${2:-us-east4}"

# ---------------------------------------------------------------- helpers

if [ -t 1 ]; then
  bold=$(printf '\033[1m'); green=$(printf '\033[32m'); yellow=$(printf '\033[33m')
  red=$(printf '\033[31m'); reset=$(printf '\033[0m')
else
  bold=""; green=""; yellow=""; red=""; reset=""
fi

step() { printf '\n%s==> %s%s\n' "$bold" "$1" "$reset"; }
ok()   { printf '%s✓%s %s\n' "$green" "$reset" "$1"; }
warn() { printf '%s!%s %s\n' "$yellow" "$reset" "$1"; }
die()  { printf '%sx %s%s\n' "$red" "$1" "$reset" >&2; exit 1; }

confirm() {
  # confirm "question" -> returns 0 on yes. POPSHOT_YES=1 answers yes (for scripted re-runs).
  if [ "${POPSHOT_YES:-0}" = "1" ]; then return 0; fi
  local answer
  printf '%s?%s %s [y/N] ' "$yellow" "$reset" "$1"
  { read -r answer </dev/tty; } 2>/dev/null || answer=""
  case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

need() { command -v "$1" >/dev/null 2>&1; }

sha256_of() {
  if need shasum; then shasum -a 256 "$1" | awk '{print $1}'; else sha256sum "$1" | awk '{print $1}'; fi
}

# ---------------------------------------------------------------- 0. where we are

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "Run this from inside the popshot repo."
cd "$ROOT"
[ -f infra/terraform/bootstrap/main.tf ] || die "infra/terraform/bootstrap is missing. Pull the latest main."

if [ -z "$PROJECT_ID" ]; then
  printf 'Google Cloud project ID: '
  { read -r PROJECT_ID </dev/tty; } 2>/dev/null || die "No terminal to ask for the project ID; pass it as an argument."
fi
case "$PROJECT_ID" in
  [a-z]*[a-z0-9]) ;;
  *) die "That doesn't look like a project ID: '$PROJECT_ID'" ;;
esac

step "Popshot provisioning: project ${PROJECT_ID}, region ${REGION}"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" != "main" ]; then
  warn "You're on '$branch'. The deploy always runs from main on GitHub; local Terraform uses this checkout."
fi

# ---------------------------------------------------------------- 1. tools

step "1/7 Tools"

os="$(uname -s)"; arch="$(uname -m)"
if [ "$os" = "Darwin" ]; then
  if ! need brew; then
    die "Homebrew is needed to install gcloud and gh: https://brew.sh"
  fi
  if ! need gcloud; then
    confirm "Install the Google Cloud CLI with Homebrew?" || die "gcloud is required."
    brew install --cask gcloud-cli || brew install --cask google-cloud-sdk
  fi
  if ! need gh; then
    confirm "Install the GitHub CLI with Homebrew?" || die "gh is required."
    brew install gh
  fi
else
  need gcloud || die "Install the Google Cloud CLI: https://cloud.google.com/sdk/docs/install"
  need gh || die "Install the GitHub CLI: https://cli.github.com"
fi
need curl || die "curl is required."
need unzip || die "unzip is required."
ok "$(gcloud --version 2>/dev/null | head -1), gh $(gh --version | head -1 | awk '{print $3}')"

# Terraform: a pinned, checksum-verified copy in .tools/ (gitignored), so the version matches CI.
case "$os/$arch" in
  Darwin/arm64) tf_platform="darwin_arm64"; tf_sha="$TERRAFORM_SHA256_darwin_arm64" ;;
  Darwin/x86_64) tf_platform="darwin_amd64"; tf_sha="$TERRAFORM_SHA256_darwin_amd64" ;;
  Linux/x86_64) tf_platform="linux_amd64"; tf_sha="$TERRAFORM_SHA256_linux_amd64" ;;
  *) die "No pinned Terraform checksum for $os/$arch." ;;
esac
TOOLS="$ROOT/.tools"
TF="$TOOLS/terraform-$TERRAFORM_VERSION"
if [ ! -x "$TF" ]; then
  mkdir -p "$TOOLS"
  zip="$TOOLS/terraform_${TERRAFORM_VERSION}_${tf_platform}.zip"
  curl -fsSLo "$zip" "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_${tf_platform}.zip"
  actual="$(sha256_of "$zip")"
  if [ "$actual" != "$tf_sha" ]; then
    rm -f "$zip"
    die "Terraform download failed its checksum (got $actual). Not using it."
  fi
  unzip -q -o "$zip" terraform -d "$TOOLS"
  mv "$TOOLS/terraform" "$TF"
  chmod +x "$TF"
  rm -f "$zip"
fi
ok "Terraform $TERRAFORM_VERSION (checksum verified) at .tools/"

# ---------------------------------------------------------------- 2. sign in

step "2/7 Sign in"

if [ -z "$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)" ]; then
  gcloud auth login
fi
ok "gcloud account: $(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -1)"

# Terraform uses Application Default Credentials (your user, on this machine only).
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  gcloud auth application-default login
fi
gcloud auth application-default set-quota-project "$PROJECT_ID" >/dev/null 2>&1 || true
ok "Application Default Credentials ready"

if ! gh auth status -h github.com >/dev/null 2>&1; then
  gh auth login -h github.com -w
fi
gh_user="$(gh api user --jq .login)"
is_admin="$(gh api "repos/$REPO" --jq .permissions.admin 2>/dev/null || echo false)"
[ "$is_admin" = "true" ] || die "GitHub user '$gh_user' isn't an admin of $REPO."
ok "GitHub: $gh_user (admin of $REPO)"

# ---------------------------------------------------------------- 3. project

step "3/7 Project checks"

gcloud projects describe "$PROJECT_ID" --format='value(projectId)' >/dev/null 2>&1 \
  || die "Can't see project '$PROJECT_ID' with $(gcloud config get-value account 2>/dev/null)."
billing="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled)' 2>/dev/null || echo unknown)"
case "$billing" in
  True|true) ok "Billing is enabled" ;;
  unknown) warn "Couldn't check billing. Cloud SQL and Cloud Run need it enabled." ;;
  *) die "Billing isn't enabled on $PROJECT_ID. Enable it in the console, then re-run." ;;
esac

# The APIs Terraform itself needs before it can enable the rest.
confirm "Enable the base APIs (Service Usage, Resource Manager, IAM, Storage) on $PROJECT_ID?" \
  || die "Stopped. Nothing changed."
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com \
  iam.googleapis.com storage.googleapis.com --project "$PROJECT_ID"
ok "Base APIs enabled"

# ---------------------------------------------------------------- 4. bootstrap

step "4/7 Terraform bootstrap (state bucket, image repo, keyless GitHub identities)"

if gcloud storage buckets describe "gs://${PROJECT_ID}-tfstate" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok "State bucket gs://${PROJECT_ID}-tfstate exists"
else
  confirm "Create the Terraform state bucket gs://${PROJECT_ID}-tfstate in $REGION?" \
    || die "Stopped before creating the bucket."
fi
./infra/terraform/bootstrap/create-state-bucket.sh "$PROJECT_ID" "$REGION"

BOOT="infra/terraform/bootstrap"
printf 'project_id = "%s"\nregion     = "%s"\n' "$PROJECT_ID" "$REGION" > "$BOOT/terraform.tfvars"
"$TF" -chdir="$BOOT" init -input=false -lockfile=readonly -reconfigure \
  -backend-config="bucket=${PROJECT_ID}-tfstate" >/dev/null
# -detailed-exitcode: 0 = no changes, 2 = changes, anything else = error.
set +e
"$TF" -chdir="$BOOT" plan -input=false -detailed-exitcode -out=bootstrap.tfplan
plan_rc=$?
set -e
case "$plan_rc" in
  0) ok "Bootstrap is already up to date" ;;
  2)
    confirm "Apply this bootstrap plan?" || die "Stopped before applying. Nothing changed."
    "$TF" -chdir="$BOOT" apply -input=false bootstrap.tfplan
    ;;
  *) die "terraform plan failed (exit $plan_rc). See the error above." ;;
esac
rm -f "$BOOT/bootstrap.tfplan"

out() { "$TF" -chdir="$BOOT" output -raw "$1"; }
WIF_PROVIDER="$(out workload_identity_provider)"
GCP_PLAN_SA="$(out plan_service_account)"
GCP_BUILD_SA="$(out build_service_account)"
GCP_DEPLOY_SA="$(out deploy_service_account)"
TF_STATE_BUCKET="$(out state_bucket)"
IMAGE_REPOSITORY="$(out image_repository)"
ok "Bootstrap outputs read"

# The deploy's plan job runs as a read-only identity. On a missing state, Terraform's
# GCS backend takes a lock and writes an empty state even with -lock=false, which that
# identity can't do. So create the empty platform state here, with your credentials.
# (The services stack is only touched by the deploy identity, which can write state.)
PLATFORM="infra/terraform/prod/platform"
if gcloud storage objects describe "gs://${TF_STATE_BUCKET}/prod/platform/default.tfstate" >/dev/null 2>&1; then
  ok "Platform state exists"
else
  "$TF" -chdir="$PLATFORM" init -input=false -lockfile=readonly -reconfigure \
    -backend-config="bucket=${TF_STATE_BUCKET}" >/dev/null
  # Loading the state is what creates it; the listing itself is empty.
  "$TF" -chdir="$PLATFORM" state list >/dev/null 2>&1 || true
  gcloud storage objects describe "gs://${TF_STATE_BUCKET}/prod/platform/default.tfstate" >/dev/null 2>&1 \
    || die "Couldn't create the empty platform state in gs://${TF_STATE_BUCKET}."
  ok "Empty platform state created"
fi

# ---------------------------------------------------------------- 5. GitHub

step "5/7 GitHub environments and variables"

gh_user_id="$(gh api user --jq .id)"
cat <<EOF
This will change settings on $REPO:
  - environment prod-plan: deployments from main only
  - environment prod:      deployments from main only, required reviewer: $gh_user
  - on both: 8 variables (project, region, the 3 deploy identities, state bucket,
    image repository, Workload Identity provider). None are secrets.
EOF
confirm "Apply these GitHub settings?" || die "Stopped before changing GitHub. Re-run when ready."

put_environment() {
  # put_environment <name> <reviewers-json>
  printf '{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true},"reviewers":%s,"prevent_self_review":false}' "$2" \
    | gh api -X PUT "repos/$REPO/environments/$1" --input - >/dev/null
  # Allow only main. Already-present policies return 303/422; that's fine.
  gh api -X POST "repos/$REPO/environments/$1/deployment-branch-policies" \
    -f name=main -f type=branch >/dev/null 2>&1 || true
  ok "Environment $1"
}
put_environment prod-plan '[]'
put_environment prod "[{\"type\":\"User\",\"id\":$gh_user_id}]"

for env in prod-plan prod; do
  gh variable set GCP_PROJECT_ID   --repo "$REPO" --env "$env" --body "$PROJECT_ID"
  gh variable set GCP_REGION       --repo "$REPO" --env "$env" --body "$REGION"
  gh variable set WIF_PROVIDER     --repo "$REPO" --env "$env" --body "$WIF_PROVIDER"
  gh variable set GCP_PLAN_SA      --repo "$REPO" --env "$env" --body "$GCP_PLAN_SA"
  gh variable set GCP_BUILD_SA     --repo "$REPO" --env "$env" --body "$GCP_BUILD_SA"
  gh variable set GCP_DEPLOY_SA    --repo "$REPO" --env "$env" --body "$GCP_DEPLOY_SA"
  gh variable set TF_STATE_BUCKET  --repo "$REPO" --env "$env" --body "$TF_STATE_BUCKET"
  gh variable set IMAGE_REPOSITORY --repo "$REPO" --env "$env" --body "$IMAGE_REPOSITORY"
done
ok "Variables set on prod-plan and prod"

# The workflow-level check reads WIF_PROVIDER from the prod-plan environment. Confirm it's there.
gh variable list --repo "$REPO" --env prod-plan | grep -q '^WIF_PROVIDER' \
  || die "WIF_PROVIDER didn't land on prod-plan; check the environment in GitHub settings."

# ---------------------------------------------------------------- 6. deploy

step "6/7 First deploy"

confirm "Start the Deploy workflow now? (It still waits for your approval before changing anything.)" || {
  warn "Skipped. Start it any time: gh workflow run deploy.yml --repo $REPO --ref main"
  exit 0
}

before="$(gh run list --repo "$REPO" --workflow deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
gh workflow run deploy.yml --repo "$REPO" --ref main
run_id=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  sleep 5
  run_id="$(gh run list --repo "$REPO" --workflow deploy.yml --limit 1 --json databaseId --jq '.[0].databaseId // 0')"
  [ "$run_id" != "$before" ] && [ "$run_id" != "0" ] && break
  run_id=""
done
[ -n "$run_id" ] || die "The run didn't show up. Check: gh run list --repo $REPO --workflow deploy.yml"
run_url="https://github.com/$REPO/actions/runs/$run_id"

cat <<EOF

The deploy is running: $run_url
  1. Wait for "Build" and "Plan" to finish.
  2. Read the platform plan in the run summary.
  3. Click "Review deployments", tick prod, and approve.
This script waits until the run finishes.
EOF
if [ "$os" = "Darwin" ]; then open "$run_url" || true; fi

if ! gh run watch "$run_id" --repo "$REPO" --exit-status --interval 15; then
  die "The deploy failed. See $run_url (send me the failing step's log and I'll fix it)."
fi
ok "Deploy finished"

# ---------------------------------------------------------------- 7. done

step "7/7 Last step: turn on Google sign-in"

web_url="$(gcloud run services describe web --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)' 2>/dev/null || true)"
firebase_url="https://console.firebase.google.com/project/${PROJECT_ID}/authentication/providers"
cat <<EOF
Popshot is live${web_url:+ at $web_url}.

One click left, in the Firebase console (it creates the OAuth client, which stays out of
Terraform so its secret never lands in state):
  $firebase_url
  -> Add new provider -> Google -> Enable -> Save
Then open the web app and sign in.
EOF
if [ "$os" = "Darwin" ]; then open "$firebase_url" || true; fi
