# Decision log

All data in this project are simulated. Each entry: what, why, alternatives considered.

| # | Decision | Why | Alternatives considered |
|---|---|---|---|
| 1 | A bash build script instead of `make all` | `make` is not installed on this Windows machine; bash ships with git | Installing make: an extra step for anyone reproducing |
| 2 | Project virtual environment `.venv`, versions pinned | No packages were installed globally; keeps the build reproducible | Global install |
| 3 | Week 11 excluded as a washout | The effect is still ramping, so including it would blur the post period | Include it and estimate a smaller average effect |
| 4 | Planted truth is the steady-state effect, -1.2 min | Matches the windows above, so "bias" has one clear meaning | Time-weighted average including the ramp |
| 5 | Store-week panel for estimation | Clusters are stores either way, and weekly data are easier to read and check by hand | Store-day regression, kept only to show ordinary vs clustered SEs |
| 6 | All three methods get store-level intervals | So their failures come from the design and not from a poor SE; a fairer contest | Naive store-day SEs for the naive methods |
| 7 | t with (stores - 1) degrees of freedom | 30 clusters is few enough that a normal critical value would be too narrow | Normal critical value |
| 8 | Rain and festival are observable | They are in reality, and analysts should be able to investigate them | Hiding them, which would be unrealistic |
| 9 | Keep the planted drift in S1 | Asked for by the brief, and S1 with drift tells the truth about before/after, even though the brief expected every method to work in S1 | Removing drift from S1 so before/after "works", which would favour a method |
| 10 | S3's shock raises delivery time | Heavy rain is the shock the brief names and rain slows deliveries, so the pilot looks worse than it is. It tests whether a real gain gets wrongly rejected | A favourable shock that fakes a win: same bias size, opposite sign |
| 11 | S2 selects on weeks 7-10, 15 stores | An ops lead looks at a recent dashboard; 15 keeps power comparable across scenarios | Fewer stores, which would raise bias |
| 12 | Measured MDE by calibrating to two measured facts | The simple lag-1 correlation gave persistence 0.23 and MDE 0.513, too optimistic when compared with the actual SE. Failure logged in the pre-registration | Bias-correcting the correlation; a pure placebo SD with no way to vary window length |
| 13 | High-precision check of 2,000 replications | S1 DiD bias of -0.057 looked larger than chance at 200 runs and had no mechanism. At 2,000 runs it is -0.008, within noise | Reporting the 200-run figure unexamined, or re-rolling seeds (never acceptable) |
| 14 | Report "before/after understates", not "overstates" | The brief's example headline assumed overstatement. Here the planted drift pushes delivery times up, so before/after understates. Truth over the template | Re-tuning the simulator to produce the expected headline |
| 15 | Guardrail breach in A/B uses raw p, not Holm | Missing real harm is the costlier mistake for a guardrail. Holm is still reported, and here both agree | Holm for everything |
| 16 | Guardrail RAG on point estimates | Simple enough to run weekly in a spreadsheet. Weakness: a noisy guardrail can look green; the interval is reported alongside | Using interval bounds |
| 17 | Keep anomaly threshold at the pre-registered 3 despite poor precision | Changing it after seeing results would break pre-registration. The weak precision is reported as a finding | Tuning the threshold to look good |
| 18 | Streak rule kept as exploratory | It raised precision but lost most recall, because the first incident day inflates the baseline for the next day. Not recommended as is | Excluding flagged days from the baseline: left as future work |
| 19 | CUPED also with log spend | Prior spend is very skewed; the brief asks for raw spend, reported first. Log is a one-line check | Winsorising spend |
| 20 | Tracker verified with the `formulas` Python library | LibreOffice is not installed here, and Excel cannot be driven. So formulas were recalculated by an independent engine, but the file has **not** been opened in Excel or Google Sheets | Installing LibreOffice |
| 21 | No company names, no real benchmarks | The brief forbids the first, and unverifiable benchmarks are worse than labelled assumptions | Citing industry figures from memory |
| 22 | Charts are static PNGs | Must embed in one self-contained HTML, and they live in a repo | Interactive charts, which add a JavaScript dependency |

## Future work: deliberately not built

The brief keeps this project to methods that can be explained from scratch.

| Method | What it would add | Why it is left out |
|---|---|---|
| Stratified assignment by city | Would directly prevent S3's imbalance | **The first thing to do in a real pilot.** It is a design change, so S3 stays as a warning |
| DiD with city x week effects | Would absorb S3's city shock if each city has both treated and control stores | Goes beyond the listed methods. Cannot work when a city has too few control stores |
| Synthetic control | A better control group when treated units are few or unusual | Advanced; out of scope |
| Staggered-adoption estimators | Needed if stores start at different dates | The design has one common start |
| Wild cluster bootstrap | Better intervals with very few clusters | The permutation test already gives a simple check |
| Sequential testing | Allows valid peeking | A fixed horizon is the simple fix |
| Heterogeneous effects | Which store types gain most | The simulator plants one common effect, so there is nothing to find |
