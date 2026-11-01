# SQL skills checklist

Where each skill actually appears in this project's SQL. All data are simulated.

| Skill | File | View | What it does |
|---|---|---|---|
| [x] INNER JOIN | `sql/01_staging.sql` | `dim_store`, `stg_store_day` | Attaches city, assignment, calendar and weather |
| [x] LEFT JOIN (anti-join) | `sql/02_quality_checks.sql` | `dq_missing_store_days` | Finds store-days that should exist but do not |
| [x] CROSS JOIN | `sql/02_quality_checks.sql` | `dq_missing_store_days` | Builds every expected store x date |
| [x] CTE | `sql/01_staging.sql`, `03`, `04`, `06` | `stg_store_day`, `ab_srm_check`, `store_week_wow`, `anomaly_store_day` | Breaks queries into named steps |
| [x] ROW_NUMBER | `sql/01_staging.sql` | `stg_store_day` | Keeps one row per store-day when rows were double-loaded |
| [x] RANK | `sql/03_balance_and_srm.sql` | `rank_worst_stores` | Ranks stores by recent delivery time |
| [x] LAG | `sql/04_baselines.sql` | `store_week_wow` | Week-over-week change per store |
| [x] LAG and LEAD | `sql/06_anomaly_flags.sql` | `anomaly_incident_candidates` | Looks at the days either side of a flag |
| [x] Rolling frame | `sql/04_baselines.sql` | `store_day_baseline` | 7-day baseline, `ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING` |
| [x] Rolling frame with FILTER | `sql/06_anomaly_flags.sql` | `anomaly_store_day` | Trailing 28-day mean and SD of normal days only |
| [x] Conditional aggregation (`CASE`) | `sql/03_balance_and_srm.sql` | `balance_city` | Counts treated and control stores per city |
| [x] Conditional aggregation (`FILTER`) | `sql/05_weekly_scorecard.sql` | `weekly_scorecard_inputs` | Treated and control sums side by side |
| [x] HAVING | `sql/02_quality_checks.sql` | `dq_duplicates` | Finds store-days loaded more than once |
| [x] Scalar subqueries | `sql/02_quality_checks.sql` | `dq_summary` | One line per scenario of check counts |
| [x] Named WINDOW clause | `sql/04_baselines.sql`, `06` | `store_day_baseline` | Reuses one window definition |
| [x] Ratio of sums | Every metric view | `store_week_panel` | See `docs/METRICS.md` |
