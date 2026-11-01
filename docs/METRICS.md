# Metric definitions

All data in this project are simulated. Rates are always **ratio of sums**, never an average of averages. A busy
store-day should count for more than a quiet one, and a ratio of sums does that automatically.

| Metric | Grain computed at | Numerator | Denominator | Good direction | Role |
|---|---|---|---|---|---|
| Mean delivery time (min) | store-week, group-week | `SUM(delivery_minutes_total)` | `SUM(orders)` | Lower | Pilot primary |
| Order defect rate (%) | store-week, group-week | `SUM(late + missing_item + cancelled)` | `SUM(orders)` | Lower | Pilot secondary |
| Rider idle share (%) | store-week, group-week | `SUM(rider_idle_minutes)` | `SUM(rider_shift_minutes)` | Lower | Pilot guardrail |
| Refund rate (%) | store-week, group-week | `SUM(refunded_orders)` | `SUM(orders)` | Lower | Pilot guardrail |
| Orders per store-day | group, pre-period | `SUM(orders)` | store-days observed | n/a | Balance check |
| Conversion (%) | arm | users with `converted = 1` | users in arm | Higher | A/B primary |
| Revenue per user | arm | `SUM(revenue)` | users in arm, **including** non-buyers | Higher | A/B secondary |
| Refund rate per user (%) | arm | users with `refunded = 1` | users in arm | Lower | A/B guardrail |

## One subtlety to know

The DiD estimator averages store-week means, so each **store** counts equally. That is deliberate: the store was the
thing assigned, and the regression's question is "what did the average treated store gain?". The tracker's pooled
scorecard instead sums everything first, so it weights by **orders**. It is the right view for a weekly operations
monitor but gives a slightly different number, which is why the tracker's Decision tab takes the store-level estimate.

## Why ratio of sums: a tiny example

| Day | Orders | Delivery minutes | Daily mean |
|---|---|---|---|
| 1 | 100 | 1,500 | 15.0 |
| 2 | 300 | 5,400 | 18.0 |

- Average of daily means: (15.0 + 18.0) / 2 = 16.5 minutes. This treats the quiet day as equal to the busy day.
- Ratio of sums: 6,900 / 400 = 17.25 minutes. This is what the average customer experienced.
