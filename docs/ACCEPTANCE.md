# Acceptance record

Engineering tests use synthetic fixtures and mocked API responses. They do not establish live provider access or business performance.

| Milestone | Evidence required | Initial status |
|---|---|---|
| Parsing, budget and replay integrity | Automated tests including rounded counts, exact date pairs, resets, vendor changes and ambiguous starts | 34 local checks passed on 2026-10-16; GitHub-hosted CI independently validates the suite. Includes actual Git repository regression for old-workflow reruns and visible daily Agent budget exhaustion |
| Prediction workflow | Chronological maturity purges, baseline comparison, synthetic end-to-end evaluation | Synthetic notebook executed sequentially locally; hosted Colab execution and real model performance remain unverified |
| Agent workflow | Actual LangGraph execution with mocked tool-calling model, five-call cap, invalid evidence rejection | Gemini credential and live research tool calls verified; first live Agent attempt reached five calls without a valid final selection and fell back to rules. Output schema tightened; live finalization remains unverified |
| Dashboard and images | Browser interaction checks and PNG inspection | Local PNG export passed; deployed browser interaction checks pending |
| GitHub publication | Verified public source and Pages deployment | Source tests, manual cloud collection, private checkpoints, live snapshot publication and the triggered Pages deployment succeeded on 2026-10-16; public JSON verified against private run state |
| Real MY/TH/VN samples | Private vendor run IDs, correct schema and public timestamps | First manual cloud collection on 2026-10-16 returned 27 accepted records: 9 per market and 3 per market/category query; raw snapshots and budget ledger saved privately |
| Three daily unattended runs | Three distinct scheduled dates with successful country-level results | Pending elapsed scheduled runs |
| Real forecast performance | 84 dates, 500 mature labels, held-out errors | Not eligible; one real observation date so far |
| Efficiency gain | Ten accepted paired manual/automated timings | Not measured |
| Brand incubation / sales loop | Real brand, listing, campaign and sales records | Outside this first research-system delivery |

Do not replace pending milestones with synthetic results. The live dashboard, private run history and the deployed commit are the operational evidence sources.
