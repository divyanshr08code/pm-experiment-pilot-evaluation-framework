# Tracker guide: `outputs/pilot_tracker.xlsx`

The file ships filled with **simulated** data from scenario S1. Yellow cells are inputs. Everything else is a live formula.

| Tab | What it does | What you do |
|---|---|---|
| Guide | Orientation | Read once |
| Inputs | Raw weekly sums for treated and control | Paste one new row a week, from `sql/05_weekly_scorecard.sql` (`weekly_scorecard_inputs`) |
| Scorecard | Weekly gap, effect vs pre-period gap, RAG for each guardrail, count of Red weeks in a row | Read it |
| Rubric | Pre-registered thresholds and rules | Change only with a dated deviation |
| Decision | Applies the rubric to the formal estimate; shows stop-loss status | Paste estimate, bounds, pre-trend p and guardrail estimates from `analysis/run_pilot.py` |
| Milestones_Risks | Plan and risk log; risk score = likelihood x impact | Update statuses |
| Status_Update | Template that pulls current numbers | Fill in the yellow cells and send |

## Using it on a real pilot

1. Replace the rows in Inputs with your baseline weeks. The `period` column must say `pre`, `ramp` or `post`, since the formulas key on it.
2. Set the thresholds in Rubric from your own pre-registration.
3. Each week: run the data-quality checks, paste the new row, then read guardrails and stop-loss.
4. A weekly "Effect vs pre gap" is noisy. **Do not read it as a result.** It exists to spot harm early.
5. At the read date, run the store-level regression and put its numbers in Decision.
6. To add weeks beyond 20, extend the ranges in Scorecard. Formula ranges cover the rows present when the file was built.

## How it was built and checked

`reporting/build_tracker.py` writes it with openpyxl, using only IF, OR, AVERAGEIF, COUNTIF and arithmetic, all of which exist in Excel and Google Sheets.

**Calculated values:** openpyxl saves formulas with no results, so the build calculates every formula with the `formulas` Python library and stores each result beside its formula. Viewers that do not calculate therefore still show numbers, and the formulas stay live. `tests/test_tracker.py` checks this, and checks the results against the Python rubric and an independent calculation from the raw weekly sums.

**Not verified:** Excel and Google Sheets were not available during the build, so behaviour inside those two applications has not been tested by the build.

The pooled scorecard weights by orders, while the Decision tab's estimate weights stores equally, so the two differ slightly. See `docs/METRICS.md`.
