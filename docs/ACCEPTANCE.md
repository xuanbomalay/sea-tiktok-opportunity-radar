# Acceptance record

Engineering tests use synthetic fixtures and mocked API responses. They do not establish live provider access or business performance.

| Milestone | Evidence required | Initial status |
|---|---|---|
| Parsing, budget and replay integrity | Automated tests including rounded counts, exact date pairs, resets, vendor changes and ambiguous starts | 32 local automated tests passed on 2026-10-16; mocked providers only |
| Prediction workflow | Chronological maturity purges, baseline comparison, synthetic end-to-end evaluation | Synthetic notebook executed sequentially locally; hosted Colab execution and real model performance remain unverified |
| Agent workflow | Actual LangGraph execution with mocked tool-calling model, five-call cap, invalid evidence rejection | Mocked integration tested; live API pending key |
| Dashboard and images | Browser interaction checks and PNG inspection | Local PNG export passed; deployed browser interaction checks pending |
| GitHub publication | Verified public source and Pages deployment | Verify deployment run |
| Real MY/TH/VN samples | Private vendor run IDs, correct schema and public timestamps | User reports all three Secrets saved; live smoke tests pending |
| Three daily unattended runs | Three distinct scheduled dates with successful country-level results | Pending elapsed scheduled runs |
| Real forecast performance | 84 dates, 500 mature labels, held-out errors | Not eligible; no validated live history yet |
| Efficiency gain | Ten accepted paired manual/automated timings | Not measured |
| Brand incubation / sales loop | Real brand, listing, campaign and sales records | Outside this first research-system delivery |

Do not replace pending milestones with synthetic results. The live dashboard, private run history and the deployed commit are the operational evidence sources.
