# Design: ephemeral self-hosted runners on AWS

Status: proposal. Not deployed from this repository (see [Why not here](#why-not-here)).

## When GitHub-hosted runners stop being enough

Hosted runners cover this repo today. Self-hosted runners earn their keep when CI needs:

- **Private network access.** Integration and contract tests against services, databases or queues inside a VPC, not just the public API.
- **Stable egress IPs.** Third-party APIs (market data, settlement, payment providers) that allow-list callers.
- **Different hardware or cost profile.** Larger or ARM instances, spot pricing, warm caches for heavy suites.

## Options

| | CodeBuild-managed GitHub runners | `terraform-aws-github-runner` on EC2 | Actions Runner Controller on EKS |
|---|---|---|---|
| What you run | nothing: CodeBuild starts a runner per job | webhook → Lambda scale-up → EC2 (spot) per job | runner pods on an existing cluster |
| Ops effort | lowest | medium (module upgrades, AMIs) | low only if you already run EKS |
| VPC access | yes (project in VPC) | yes | yes |
| Fits when | a few VPC-bound jobs | many jobs, cost-sensitive, custom AMIs | the platform is already Kubernetes |

**Recommendation:** start with CodeBuild-managed runners for the handful of jobs that need the VPC. Move to the Terraform module only if queue time or cost show it's worth owning a fleet.

## Guardrails (any option)

- **Ephemeral:** one job per runner, then destroyed. No state leaks between jobs or repos.
- **Never for untrusted code:** self-hosted labels only on `push` to `main` and on PRs from branches in the repo, never from forks. Enforce with runner groups restricted to selected repositories.
- **Credentials:** no static keys on runners. The instance or CodeBuild role gets only what CI needs, and deploys still assume a separate role via OIDC.
- **Network:** private subnets, VPC endpoints for S3, ECR and CloudWatch Logs, NAT only where egress allow-lists require it. IMDSv2 required.
- **Cost:** scale to zero, spot where interruptions are tolerable, a hard `maximum count`, and a budget alarm.
- **Observability:** job queue time and runner start time as CloudWatch metrics. Alert on queue time, the first sign the fleet is too small.

## Sketch (Terraform, EC2 option)

Illustrative only. Pin the module version and check its variables before use.

```hcl
module "runners" {
  source  = "github-aws-runners/github-runner/aws"
  # version = "x.y.z"

  prefix     = "pqg-ci"
  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  github_app = {
    id             = var.github_app_id
    key_base64     = var.github_app_key_base64
    webhook_secret = var.webhook_secret
  }

  enable_ephemeral_runners = true
  instance_types           = ["m7g.large", "m6g.large"] # ARM, spot-friendly
  runners_maximum_count    = 10
  runner_extra_labels      = ["vpc"]
}
```

Jobs opt in with `runs-on: [self-hosted, vpc]`. Everything else stays on hosted runners.

## Why not here

- The repository is public: a self-hosted runner reachable from a public repo is a standing risk, and there is nothing in a VPC to reach yet.
- The demo AWS account sits in an AWS-managed organization whose SCPs block creating an IAM OIDC provider, which is also why the deploy job uses a least-privilege IAM user instead of OIDC. In a normal account the same template (`AuthMode=oidc`) gives short-lived credentials restricted to `main`.
