-- Question: what does the clean, de-duplicated store-day table look like?
-- Grain: stg_store_day = one row per scenario x store x date.
-- Metrics: raw counts only. Rates are computed later as ratio of sums (docs/METRICS.md).
-- All data are simulated.

CREATE OR REPLACE VIEW raw_store_day AS
SELECT * FROM read_csv_auto('data/observed/store_day_raw.csv', header = true);

CREATE OR REPLACE VIEW dim_store AS
SELECT d.scenario, d.store_id, d.city, d.size_class, d.baseline_throughput, a.treated
FROM read_csv_auto('data/observed/store_dim.csv', header = true) AS d
JOIN read_csv_auto('data/observed/pilot_assignment.csv', header = true) AS a
  USING (scenario, store_id);

CREATE OR REPLACE VIEW dim_calendar AS
SELECT
    CAST(date AS DATE) AS date,
    week, is_weekend, is_festival,
    -- Pre-registered windows. Week 11 is the ramp-in washout, so it belongs to neither period.
    CASE WHEN week <= 10 THEN 'pre' WHEN week = 11 THEN 'ramp' ELSE 'post' END AS period
FROM read_csv_auto('data/observed/calendar.csv', header = true);

CREATE OR REPLACE VIEW city_weather AS
SELECT scenario, city, CAST(date AS DATE) AS date, is_rain
FROM read_csv_auto('data/observed/city_weather.csv', header = true);

-- ROW_NUMBER keeps exactly one row per store-day, so double-loaded rows cannot double count.
-- Impossible values are removed here and counted in 02_quality_checks.sql.
CREATE OR REPLACE VIEW stg_store_day AS
WITH numbered AS (
    SELECT
        r.*,
        ROW_NUMBER() OVER (PARTITION BY scenario, store_id, date ORDER BY orders DESC) AS copy_number
    FROM raw_store_day AS r
)
SELECT
    n.scenario, n.store_id, CAST(n.date AS DATE) AS date,
    s.city, s.size_class, s.treated,
    c.week, c.period, c.is_weekend, c.is_festival, w.is_rain,
    n.orders, n.delivery_minutes_total,
    n.late_orders + n.missing_item_orders + n.cancelled_orders AS defective_orders,
    n.rider_idle_minutes, n.rider_shift_minutes, n.refunded_orders
FROM numbered AS n
JOIN dim_store AS s USING (scenario, store_id)
JOIN dim_calendar AS c ON c.date = CAST(n.date AS DATE)
JOIN city_weather AS w ON w.scenario = n.scenario AND w.city = s.city AND w.date = CAST(n.date AS DATE)
WHERE n.copy_number = 1
  AND n.delivery_minutes_total > 0
  AND n.orders > 0;
