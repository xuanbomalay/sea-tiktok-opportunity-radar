# Deployment, accounts and recovery

## Repositories

Public code: `xuanbomalay/sea-tiktok-opportunity-radar`.

Private state/scheduler: `xuanbomalay/sea-tiktok-radar-data`. Copy `deployment/private/daily.yml` to `.github/workflows/daily.yml`, `deployment/private/gitignore` to `.gitignore`, and the private README into that repository. These contain no credentials.

Enable GitHub Pages in the public repository: **Settings → Pages → Source: GitHub Actions**. The public `pages.yml` workflow displays an existing `gh-pages` snapshot, or builds an honest empty page and a separately labeled synthetic demonstration if none exists.

## Required credentials (never paste secrets into a chat or notebook output)

In the **private repository → Settings → Secrets and variables → Actions**, add:

| Secret | Account / minimum access |
|---|---|
| `APIFY_TOKEN` | Your Apify Free account. Use a dedicated project account if other workloads consume its allowance. No paid subscription or overage. |
| `RADAR_PUBLISH_TOKEN` | Fine-grained GitHub token for **only the public radar repository**, **Contents: read and write**. It updates `gh-pages` and sends `repository_dispatch`; it does not need private-repository, administration or workflow-file write access. |
| `GEMINI_API_KEY` | Optional unbilled Google AI Studio project in a supported region. Only public computed metrics are sent. The data pipeline remains usable without it. |

A GitHub connector login is not automatically a credential that a scheduled GitHub Action can reuse. The narrowly scoped publication token is needed for the private-to-public handoff. Account owners must complete account/terms/security checks and enter secrets in the service's protected UI. Configure token expiry and replace an expired secret; no credentials are kept in source control.

The publication Token's selected repository is the **public `sea-tiktok-opportunity-radar`**. Its Secret is stored in the **private `sea-tiktok-radar-data`**. These are intentionally different: the private workflow needs permission to write the public destination. Selecting only the private repository in the Token settings causes publication HTTP 403 even when Contents has read/write access.

## First live run

1. Set the private secrets and confirm Pages is configured.
2. Open private **Actions → Daily sampled market research → Run workflow**.
3. Inspect the private run and `private/last_attempt.json`: MY, TH and VN must each return the expected market, product identifiers and counters. Price/seller omissions must remain visible as missing.
4. Inspect provider run cost and actual returned schema against the documentation. Document deviations before interpreting metrics.
5. Confirm the public page shows real observation timestamps, updated health and matching chart/CSV values.
6. Observe three separate daily scheduled runs before accepting unattended daily operation.

The schedule is 01:23 UTC / 09:23 Asia/Shanghai. GitHub may delay scheduled runs. Review account-wide free Actions minutes and artifact use. Standard hosted runners and default free limits are intended; do not enable paid overage for this project.

## Cost and retry policy

- Reserve result slots and micro-dollar budget under an atomic SQLite transaction before each API start. Push this reservation to the private Git repository before the external side effect on GitHub runners.
- Each API run also receives `maxTotalChargeUsd`. Initial discovery includes neither reviews nor detail enrichment.
- Preserve conservative reservations for empty, failed and uncertain starts; a rerun cannot reset the budget. Month uses the local scheduled date's calendar month, conservatively separate from the vendor's billing cycle.
- GET requests retry at most twice for network, 429 and server failures. POST starts are not automatically retried. An unknown start is not sent to another provider.
- A complete prior query is reused on same-day reruns. Empty/schema-error terminal queries may use the fallback, within the same daily/monthly limits.
- The account's independent usage and data-storage/read costs can reduce free availability before this project's cap; leave the account on its free plan and inspect its billing dashboard.

## Recovery

- `needs_credentials`: add the secret. No market findings exist yet.
- `manual_reconciliation_required`: inspect Apify runs for the matching country/query/time. Never delete the reservation or repeat the POST blindly. After identifying the real run ID, reconcile the private ledger through a reviewed change and resume retrieval.
- `pending_run` / transient GET error: rerun; the persisted run ID is polled and reused.
- `schema_error`: inspect the private raw envelope, update only the relevant adapter and contract fixture, rerun tests, then reconcile/replay the saved envelope.
- `budget_exhausted` / `daily_budget_exhausted`: preserve last good data and wait for reset. No automatic paid upgrade.
- Expired publication token: collection history remains private and checkpointed; renew the scoped token and rerun publication.
- Publication HTTP 403: check the Token's selected public repository and Contents read/write permission. Editing the original Token's permissions does not require a new Secret value; regenerating the Token does. Error logs identify the failed HTTP operation without printing credentials.
- Rendering failure: no new partial directory is published; the current public site remains available.

To stop collection, disable the private workflow in GitHub Actions. The existing public page remains readable and will show stale observation timestamps. GitHub's normal notification preferences govern workflow failure notifications; this project sends no email or chat messages itself.
