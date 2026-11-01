-- Question: were treated and control comparable before the pilot, and did the A/B split work?
-- Grain: balance_pre_period = scenario x treated group. balance_city = scenario x city.
--        rank_worst_stores = scenario x store. ab_srm_check = A/B variant.
-- Metrics: ratio of sums over pre-period days. All data are simulated.

CREATE OR REPLACE VIEW balance_pre_period AS
SELECT
    scenario,
    treated,
    COUNT(DISTINCT store_id) AS stores,
    SUM(delivery_minutes_total) / SUM(orders) AS mean_delivery_min,
    100.0 * SUM(defective_orders) / SUM(orders) AS defect_rate_pct,
    100.0 * SUM(rider_idle_minutes) / SUM(rider_shift_minutes) AS rider_idle_pct,
    100.0 * SUM(refunded_orders) / SUM(orders) AS refund_rate_pct,
    SUM(orders) * 1.0 / COUNT(*) AS orders_per_store_day
FROM stg_store_day
WHERE period = 'pre'
GROUP BY scenario, treated
ORDER BY scenario, treated;

-- Conditional aggregation: this one table exposes the S3 trap (treated stores bunched in one city).
CREATE OR REPLACE VIEW balance_city AS
SELECT
    scenario, city,
    SUM(CASE WHEN treated = 1 THEN 1 ELSE 0 END) AS treated_stores,
    SUM(CASE WHEN treated = 0 THEN 1 ELSE 0 END) AS control_stores
FROM dim_store
GROUP BY scenario, city
ORDER BY scenario, city;

-- RANK shows how the treated stores sit on the league table of recent performance (the S2 trap).
CREATE OR REPLACE VIEW rank_worst_stores AS
WITH recent AS (
    SELECT scenario, store_id, treated, SUM(delivery_minutes_total) / SUM(orders) AS recent_delivery_min
    FROM stg_store_day
    WHERE week BETWEEN 7 AND 10
    GROUP BY scenario, store_id, treated
)
SELECT *, RANK() OVER (PARTITION BY scenario ORDER BY recent_delivery_min DESC) AS slowest_rank
FROM recent;

CREATE OR REPLACE VIEW ab_users AS
SELECT * FROM read_csv_auto('data/observed/ab_users.csv', header = true);

-- Sample ratio check. Chi-square against an intended 50/50 split; the p-value is computed in Python.
CREATE OR REPLACE VIEW ab_srm_check AS
WITH counts AS (
    SELECT
        variant,
        COUNT(*) FILTER (WHERE arm = 'treatment') AS n_treatment,
        COUNT(*) FILTER (WHERE arm = 'control') AS n_control
    FROM ab_users
    GROUP BY variant
)
SELECT
    variant, n_treatment, n_control,
    100.0 * n_treatment / (n_treatment + n_control) AS treatment_share_pct,
    POWER(n_treatment - (n_treatment + n_control) / 2.0, 2) / ((n_treatment + n_control) / 2.0)
      + POWER(n_control - (n_treatment + n_control) / 2.0, 2) / ((n_treatment + n_control) / 2.0) AS chi_square
FROM counts
ORDER BY variant;
