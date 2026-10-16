# Data Card

## Population, sampling and provenance

- Target: public TikTok Shop product search results in MY / TH / VN.
- Queries: fixed localized strings in `config.toml`; nine market–niche pairs, three returned listings per query initially.
- Niches: home storage, kitchen tools, pet accessories. Queries are broad research seeds, not a verified market taxonomy.
- This is a convenience sample of ranked search results. Selection bias, localization, seller dominance and vendor coverage limit inference.
- Raw envelopes are private. Each normalized row retains provider, run ID, request keyword, UTC observation time and SHA-256 of the vendor row.
- The observation date is UTC; collection is scheduled at 09:23 Asia/Shanghai. Run completion time, not a claimed earlier historical date, timestamps a live observation.
- No buyer contact information or personal reviews are requested. Public assets exclude raw snapshots, run IDs, seller identifiers and API keys.

## Source register (documentation checked 2026-10-16)

| Source | Purpose and limitation |
|---|---|
| [Coregent actor README](https://apify.com/coregent/tiktok-shop-product-scraper) / [input](https://apify.com/coregent/tiktok-shop-product-scraper/input-schema) / [pricing](https://apify.com/coregent/tiktok-shop-product-scraper/pricing) | Primary provider; a manual cloud run on 2026-10-16 returned 27 accepted records across all nine MY/TH/VN query pairs. Free-tier base product event is currently $0.004. Discovery only; detail/review enrichment disabled. |
| [TicTech actor documentation](https://apify.com/tictechid/vanzi-tiktok-shop) | Fallback; `mode=search`, lower-case `region`, `search_keywords`, `max_items`. It can omit price/seller fields. Do not invent missing metrics. |
| [Apify pricing](https://apify.com/pricing) | $5/month free allowance at verification time. Account-wide use, storage and reads also consume allowance. Free accounts stop when exhausted. |
| [Apify run API](https://docs.apify.com/api/v2/actors-runs-post) | `maxTotalChargeUsd` caps each run. Non-idempotent starts are never automatically retried after an uncertain response. |
| [TikTok Shop API](https://partner.tiktokshop.com/docv2/api-document) | Authorized seller/partner access is not assumed to provide a whole-market competitor dataset. |
| [TikTok Research FAQ](https://developers.tiktok.com/docs/en/research-api-faq) | Commercial users are not eligible for Research Tools. This project does not depend on Research API access. |
| [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing) | Optional free-tier agent. Only computed public metrics are submitted; free-tier content may be used to improve the provider's products. |

The existence of a third-party API is not proof of its accuracy, availability or permission to redistribute its datasets. Raw vendor data are not published under the code license. Confirm intended public outputs against the applicable provider/source terms before live publication.

## Normalized interface

`observed_at`, `date`, `country`, `niche`, `query`, `product_id`, `title`, `seller_id`, `price`, `currency`, `rating`, `url`, `source`, `source_run_id`, `raw_sha256`, `sold_raw`, `sold_count`, `sold_precision`.

- `sold_count`: populated only for an exact integer-form counter as returned by the provider; this is not an independent verification of the original TikTok display or audited orders. Provider-side rounding before delivery cannot be recovered without an original display string.
- `sold_precision`: `exact`, `lower_bound`, `unverified`, `missing`. For `1K+`, the numeric training value is null, with the raw display preserved.
- Unknown seller, price or rating: null, not zero. Wrong-market records or currency conflicts are rejected.
- Same date/country/niche/product is inserted once. Provider changes break growth/label continuity.

## Replay input

```json
{
  "synthetic": false,
  "country": "MY",
  "niche": "storage",
  "query": "original query",
  "source": "original provider",
  "run_id": "original private run id",
  "observed_at": "2026-10-16T01:23:00Z",
  "rows": []
}
```

Supply one envelope or an array. Keep live replay files private. Generated fixtures require `synthetic: true` and CLI `--synthetic`; state domains cannot be mixed. Replay does not reconstruct old information availability unless original timestamps/provenance exist.

## Public output

`data/latest.json` is the dashboard interface, with schema version, live/demo mode, latest observation, group summaries, trend summaries, latest candidate metadata, evaluation and health state. `data/summary.csv`, `data/report.md` and `charts/*.png` are generated from the same snapshot. They do not contain the private raw panel.
