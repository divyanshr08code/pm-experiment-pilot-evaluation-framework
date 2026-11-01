# SOP: running an operations pilot

Written alongside a simulation study; a template to adapt, not a record of a real program.

**Purpose:** decide whether to scale a pilot, with rules fixed before anyone sees results. **Owner:** program owner.

| Step | When | Who | Do | Done when |
|---|---|---|---|---|
| 1. Pre-register | Before assignment | Analyst, program owner | Write hypothesis, primary metric, guardrails, method, MDE and decision rubric. Commit with a timestamp | Sponsor has signed off |
| 2. Assign | Before go-live | Analyst | Draw stores at random, stratified by city. Run the balance table. Lock the list | Balance table reviewed; list locked |
| 3. Check instrumentation | At least 2 weeks before go-live | Analyst | Run `sql/02_quality_checks.sql`: missing store-days, duplicates, impossible values. Confirm every metric can be computed | No open faults |
| 4. Go live | Start date | Store ops lead | Make the change in treated stores only. Log the date per store | Compliance confirmed for each store |
| 5. Weekly review | Every week, same day | Program owner | Run DQ checks first. Update the tracker. Review anomaly flags. Check guardrails. **Do not call success or failure** | Status update sent |
| 6. Escalate | As triggered | See below | Follow the escalation path | Logged in the risk log |
| 7. Go/no-go | Pre-registered read date | Sponsor, program owner, analyst | Apply the rubric as written. Record the decision and any dissent | Decision minuted |
| 8. Post-mortem | Within 2 weeks of the decision | Program owner | What held, what surprised us, what to change in this SOP | Notes filed; SOP updated |

## Escalation path

| Trigger | First contact | Within | Then |
|---|---|---|---|
| Data-quality fault | Analyst | Same day | Freeze the read until fixed |
| Unexplained anomaly at a store | Store ops lead | 1 day | Add to the risk log |
| One guardrail Red | Program owner | 1 day | Watch closely next week |
| Guardrail Red 2 weeks in a row | Sponsor | Same day | Stop-loss: pause expansion |
| Assignment changed after locking | Sponsor | Same day | Log a deviation; the analyst re-assesses validity |

## Rules that do not bend

- Metrics are ratios of sums.
- No early success calls. Stopping for harm is allowed; stopping for a win is not.
- Any change to thresholds or windows goes in a dated Deviations section. The original text stays.
- A sample ratio mismatch in an A/B test voids the read until the cause is found.
