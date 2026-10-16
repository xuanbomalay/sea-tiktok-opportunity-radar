# Private data and scheduler

This repository stores confidential raw vendor snapshots, the acquisition ledger and normalized observations for the public [SEA Radar project](https://github.com/xuanbomalay/sea-tiktok-opportunity-radar).

The code is loaded from the public repository. Do not make this data repository public.

Required Actions secrets:

- `APIFY_TOKEN`: Apify Free account only; do not enable paid overage.
- `RADAR_PUBLISH_TOKEN`: a fine-grained GitHub token limited to `xuanbomalay/sea-tiktok-opportunity-radar`, with **Contents: read and write** only. It publishes the sanitized `gh-pages` snapshot and dispatches the public Pages workflow. Choose an expiry and renew it when necessary.
- `GEMINI_API_KEY` (optional): a supported-region Google AI Studio **unbilled/free-tier project** key. Without it, the collector and charts work and reports are explicitly rule-based.

After setting secrets, run **Daily sampled market research → Run workflow**. Schedule: 01:23 UTC / 09:23 Asia/Shanghai. The acquisition ledger is committed before every vendor run. Never remove or roll back the ledger to reset limits; unresolved starts must be reconciled with the provider first.

Initial acceptance requires real samples in MY/TH/VN and three successful daily scheduled runs; until then, deployment is not evidence of collection success.
