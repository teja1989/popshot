# Infrastructure (`infra/terraform`)

Terraform 1.16 on Google Cloud. `bootstrap/` runs once by hand. `prod/platform` and
`prod/services` are applied by `.github/workflows/deploy.yml` on every merge to `main`, after
someone approves the plan. `prod/README.md` explains what runs where, the deploy order,
costs, and the domain. The repository-wide rules are in `/AGENTS.md`.

## Rules

- **Nothing is applied by hand.** Changes go through a PR. The deploy shows a read-only plan,
  and a person approves it before it applies. Say in the PR what the plan should show
  ("in-place update to X, nothing replaced"), so the approver can check.
- **No secrets in Terraform files, state or plans.** Generate them in Terraform and write
  them with write-only arguments (`secret_data_wo`, `root_password_wo`), or keep them in
  Secret Manager. Grant `secretAccessor` per service account, and mount them in Cloud Run
  with `secret_key_ref`.
- **A Google API key** is restricted to the APIs it calls (`api_targets`) and, for a browser
  key, to our addresses (`allowed_referrers`), like `google_apikeys_key.web` in
  `prod/platform/firebase.tf`. A server-side key lives only in Secret Manager.
- **Least privilege:** each service and job has its own service account with only the roles
  it needs. The API is internal-only, and only the web service account may invoke it.
- **Protect what can't be recreated.** The Hosting site and custom domains have
  `prevent_destroy`; the database has deletion protection. To stop managing a resource
  without deleting it, use a `removed { lifecycle { destroy = false } }` block.
- **Migrations run before new code takes traffic**, so a release must work with the
  previous code too: add first, remove later.
- **DNS lives at Cloudflare and is changed by hand**, from the `dns_records` output, so no
  Cloudflare token sits in CI.
- **Providers are pinned exactly** (`versions.tf`). Upgrade them in their own PR.
- **New spend:** say what it costs per month in the PR, and keep the budget
  (`monthly_budget_usd`) above it.

## Checks

In each stack: `terraform fmt -check -recursive`, then `terraform init -backend=false` and
`terraform validate`. CI also runs a security scan of the configuration.
