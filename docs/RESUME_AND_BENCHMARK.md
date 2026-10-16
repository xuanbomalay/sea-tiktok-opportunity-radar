# Resume claims and paired efficiency measurement

## Wording after code/deployment verification

Use only after the repository and corresponding engineering checks have been verified:

> Built a reproducible Southeast Asia TikTok Shop research pipeline with budget-controlled data adapters, matched-product trend analysis, chronological forecast evaluation, and an automated evidence dashboard; implemented a bounded tool-using agent with traceable report generation.

If live collection has not yet been verified, add:

> Validated the implementation using synthetic fixtures and mocked integrations; live-data collection and forecast performance validation are pending.

After actual live acceptance, replace the caveat with the verified country/date/coverage counts. Insert measured forecast and efficiency numbers only when the underlying reports support them. Do not infer an incubated brand or sales results from a research pipeline. The original resume PDF is intentionally not edited by this project.

## Ten paired tasks

Create a private template:

```bash
python scripts/benchmark.py private/paired_timings.csv --create-template
python scripts/benchmark.py private/paired_timings.csv
```

Choose ten comparable, distinct tasks in advance: e.g., extract a sampled country's category results, check precision/currency, compute a matched increment and produce a chart with source references. Use the same frozen inputs and acceptance rubric for manual and automated methods. Counterbalance order to reduce learning effects; record task definitions and evaluator corrections.

Record manual/automated **active human time** and **total elapsed time**, quality pass/fail, errors and corrections. Times must be positive finite values. Blank, failed-quality or incomplete pairs do not count. Before ten accepted pairs the script returns `insufficient_manual_evidence` and no efficiency ratio.

After ten accepted pairs, report median paired manual/automated ratios separately for active time and wall time, with task scope, date and sample size. A ratio of 4 would mean one-quarter of the measured time for that task definition, not four times the revenue, and is not an assumed outcome.
