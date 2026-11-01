# Pilot brief: pre-staging fast-moving SKUs

**Simulation study.** This brief is written as a program owner would write it before launch, for a simulated pilot.
Stores, people and costs are invented.

| | |
|---|---|
| **Problem** | Mean delivery time varies by store, and leadership wants it lower before peak season. Pick-and-pack is the part stores control directly. |
| **Hypothesis** | Placing the highest-velocity SKUs near the packing counter cuts picking walk time and so reduces mean delivery time, without harming riders or refunds. |
| **Intervention** | Pre-stage the 200 highest-velocity SKUs within reach of the packing counter. Refresh the list weekly. |
| **Stores** | 30 dark stores in 3 cities: 15 treated, 15 control. |
| **Assignment** | Random, drawn by the analyst, then locked. **Why:** letting ops leads pick stores invites regression to the mean (S2), and bunching in one city invites confounding (S3). In a real run, stratify by city. |
| **Primary metric** | Mean delivery time (delivery minutes / orders) |
| **Secondary metric** | Order defect rate |
| **Guardrails** | Rider idle share: Red above +2.0 pp. Refund rate: Red above +0.5 pp. |
| **Minimum detectable effect** | 0.735 min at planning (5% two-sided, 80% power, 15 stores per arm, 10 pre and 9 post weeks) |
| **Minimum worthwhile effect** | 0.5 min (assumed break-even for packing labour; **confirm with finance before a real run**) |
| **Duration** | 10-week baseline, go-live at week 11, 1-week ramp, 9 weeks of measurement |
| **Decision rubric** | `docs/PREREGISTRATION.md`, tracker tab `Rubric` |

## Data required

| Table | Grain | Fields |
|---|---|---|
| Store-day operations | store x date | orders, delivery minutes, late, missing, cancelled, refunded |
| Rider shifts | store x date | shift minutes, idle minutes |
| Store dimension | store | city, size class, baseline throughput |
| Assignment | store | treated flag, go-live date |
| Weather and calendar | city x date, date | rain flag, festival flag |

## Risks

| Risk | Mitigation |
|---|---|
| A city-level shock hits treated stores more | Stratify by city; check the balance table; review rain weeks |
| Stores are swapped in after assignment | Assignment locked; changes need the program owner's sign-off and a logged deviation |
| Packing labour rises more than assumed | Track labour hours; re-check break-even at the read date |
| Rider idle rises | Weekly RAG; stop-loss after 2 Red weeks in a row |
| Pipeline drops or duplicates rows | Weekly data-quality queries before metrics are read |
| Early peeking leads to an early call | Fixed read date; weekly reviews check safety, not success |

## Roles

| Role | Responsible for |
|---|---|
| Program owner | Brief, timeline, go/no-go meeting, escalations |
| Analyst | Pre-registration, assignment, instrumentation, scorecard, readout |
| Store ops lead | Layout changes, compliance, labour tracking |
| Fleet lead | Rider idle share, rider feedback |
| Leadership sponsor | Go/no-go decision and resourcing |

## Timeline

| Pilot week | Milestone |
|---|---|
| -4 | Pre-registration signed off |
| -3 | Stores assigned at random and locked |
| -2 | Instrumentation check passed |
| 1-10 | Baseline period |
| 11 | Go-live; ramp-in week |
| 12-20 | Measurement; weekly reviews for safety only |
| 15 | Mid-pilot review; festival week expected |
| 21 | Final readout and go/no-go meeting |
