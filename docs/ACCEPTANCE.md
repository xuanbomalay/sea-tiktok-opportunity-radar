# Acceptance record

Engineering tests use synthetic fixtures and mocked API responses. They do not establish live provider access or business performance.

| Milestone | Evidence required | Initial status |
|---|---|---|
| Parsing, budget and replay integrity | Automated tests including rounded counts, exact date pairs, resets, vendor changes and ambiguous starts | 33 tests passed locally and on GitHub-hosted Ubuntu on 2026-10-16, including an actual Git repository regression for old-workflow reruns |
| Prediction workflow | Chronological maturity purges, baseline comparison, synthetic end-to-end evaluation | Synthetic notebook executed sequentially locally; hosted Colab execution and real model performance remain unverified |
| Agent workflow | Actual LangGraph execution with mocked tool-calling model, five-call cap, invalid evidence rejection | Gemini credential and live research tool calls verified; first live Agent attempt reached five calls without a valid final selection and fell back to rules. Output schema tightened; live finalization remains unverified |
| Dashboard and images | Browser interaction checks and PNG inspection | Local PNG export passed; deployed browser interaction checks pending |
| GitHub publication | Verified public source and Pages deployment | Source, tests and initial Pages deployment succeeded; first daily snapshot publication returned HTTP 403 and awaits Token scope correction |
| Real MY/TH/VN samples | Private vendor run IDs, correct schema and public timestamps | First manual cloud collection on 2026-10-16 returned 27 accepted records: 9 per market and 3 per market/category query; raw snapshots and budget ledger saved privately |
| Three daily unattended runs | Three distinct scheduled dates with successful country-level results | Pending elapsed scheduled runs |
| Real forecast performance | 84 dates, 500 mature labels, held-out errors | Not eligible; one real observation date so far |
| Efficiency gain | Ten accepted paired manual/automated timings | Not measured |
| Brand incubation / sales loop | Real brand, listing, campaign and sales records | Outside this first research-system delivery |

Do not replace pending milestones with synthetic results. The live dashboard, private run history and the deployed commit are the operational evidence sources.
