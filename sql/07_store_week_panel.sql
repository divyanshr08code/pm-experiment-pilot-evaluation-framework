-- Question: what is the tidy table the Python estimators read?
-- Grain: one row per scenario x store x week (30 stores x 20 weeks = 600 rows per scenario).
-- Metrics: ratio of sums within store-week. All data are simulated.

CREATE OR REPLACE VIEW store_week_panel AS
SELECT
    scenario, store_id, city, size_class, treated, week, MIN(period) AS period,
    SUM(orders) AS orders,
    SUM(delivery_minutes_total) / SUM(orders) AS mean_delivery_min,
    100.0 * SUM(defective_orders) / SUM(orders) AS defect_rate_pct,
    100.0 * SUM(rider_idle_minutes) / SUM(rider_shift_minutes) AS rider_idle_pct,
    100.0 * SUM(refunded_orders) / SUM(orders) AS refund_rate_pct,
    SUM(is_rain) AS rain_days,
    COUNT(*) AS days_observed
FROM stg_store_day
GROUP BY scenario, store_id, city, size_class, treated, week
ORDER BY scenario, store_id, week;

-- Store-day extract, kept only for the "ordinary vs clustered standard errors" comparison and ICC.
CREATE OR REPLACE VIEW store_day_export AS
SELECT scenario, store_id, treated, date, week, period, delivery_minutes_total / orders AS mean_delivery_min
FROM stg_store_day
ORDER BY scenario, store_id, date;
