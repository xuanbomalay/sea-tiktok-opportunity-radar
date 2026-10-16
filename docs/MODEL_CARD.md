# Model Card

## Task and data availability

Target: **observed public sold-counter increment over the next seven calendar days**. It is not actual orders, GMV, profitability or an estimate of whole-market demand.

The same market, niche, product and provider must have exact non-decreasing observations at t and t+7. Features include exact trailing seven-day increment, preceding seven-day increment, log local price, rating, country and niche. Missing dates are not replaced with neighboring rows. A counter reset invalidates affected pairs.

Minimum gate: 84 distinct observation dates and 500 mature labeled rows. Each final split must retain at least 20 rows after purging. The gate can remain unmet if small search samples do not repeatedly observe the same products. Time elapsed alone does not guarantee readiness.

## Evaluation

- Date-grouped chronological 60% / 20% / 20% candidate splits.
- Training rows are kept only when their label end is before the first validation date. Validation labels must mature before the first test date.
- Numeric imputation/scaling and categorical encoding are fitted on training data only.
- Candidates: recent seven-day mean-rate baseline (next seven-day increment equals prior seven-day increment), Ridge, histogram gradient boosting.
- Select on validation MAE only, then report test MAE and RMSE for every model. A worse test result is retained; no promise of improvement is made.
- Fixed seed 42; every report includes input SHA-256 and split spans. Dependency versions are locked.
- Reports are rolling evaluation snapshots. Repeated snapshots are not described as a permanently untouched holdout.
- Inference uses the selected fitted model. Forecasts have explicit start/end dates and are shown separately from cumulative-counter history.

## Failure modes and limitations

Small, shifting search samples may underrepresent products, fail to form enough exact labels or be dominated by a seller. Numeric vendor counters can have undocumented approximation. Local price distributions differ by currency and market. The model cannot identify causal marketing effects or infer missing supply/fulfilment costs.

Synthetic demonstration results validate implementation, not business value. A real deployment remains `history_accumulating` until the real-data gates pass. Any future live model acceptance must report baseline-relative results on actual collected history.

## Agent boundary

The LangGraph agent reads computed metrics, compares market evidence and selects valid evidence IDs and predefined next checks. Public report sentences and numbers are rendered from that evidence; arbitrary model prose is not published as verified analysis. At most five model attempts are allowed per report day, with a persisted cache. Missing credentials, quotas or malformed responses produce an explicitly rule-based brief.
