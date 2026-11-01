-- Question: which days are abnormal, and is it rain, a festival, or something unexplained?
-- Grain: anomaly_store_day = scenario x store x date. anomaly_city_day = scenario x city x date.
-- Metric: z = (value - trailing 28-day mean of normal days) / trailing SD of normal days.
-- "Normal" = dry and non-festival, so a wet month does not hide the next wet day.
-- Flag at |z| > 3 (pre-registered). All data are simulated.

CREATE OR REPLACE VIEW anomaly_store_day AS
WITH daily AS (
    SELECT scenario, store_id, city, date, week, is_rain, is_festival, treated, period,
           delivery_minutes_total / orders AS mean_delivery_min
    FROM stg_store_day
),
scored AS (
    SELECT *,
        AVG(mean_delivery_min) FILTER (WHERE is_rain = 0 AND is_festival = 0) OVER w AS baseline_mean,
        STDDEV_SAMP(mean_delivery_min) FILTER (WHERE is_rain = 0 AND is_festival = 0) OVER w AS baseline_sd
    FROM daily
    WINDOW w AS (PARTITION BY scenario, store_id ORDER BY date ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING)
)
SELECT *,
    (mean_delivery_min - baseline_mean) / NULLIF(baseline_sd, 0) AS z_score
FROM scored
WHERE date >= (SELECT MIN(date) + INTERVAL 28 DAY FROM dim_calendar);

-- City-day roll-up averages out store noise, which is what makes city-wide shocks visible.
CREATE OR REPLACE VIEW anomaly_city_day AS
WITH daily AS (
    SELECT scenario, city, date, MAX(is_rain) AS is_rain, MAX(is_festival) AS is_festival,
           SUM(delivery_minutes_total) / SUM(orders) AS mean_delivery_min
    FROM stg_store_day
    GROUP BY scenario, city, date
),
scored AS (
    SELECT *,
        AVG(mean_delivery_min) FILTER (WHERE is_rain = 0 AND is_festival = 0) OVER w AS baseline_mean,
        STDDEV_SAMP(mean_delivery_min) FILTER (WHERE is_rain = 0 AND is_festival = 0) OVER w AS baseline_sd
    FROM daily
    WINDOW w AS (PARTITION BY scenario, city ORDER BY date ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING)
)
SELECT *, (mean_delivery_min - baseline_mean) / NULLIF(baseline_sd, 0) AS z_score
FROM scored
WHERE date >= (SELECT MIN(date) + INTERVAL 28 DAY FROM dim_calendar);

-- A flag on a dry, non-festival day points to something local to investigate.
CREATE OR REPLACE VIEW anomaly_flags AS
SELECT
    scenario, store_id, city, date, week, treated, period,
    ROUND(mean_delivery_min, 2) AS mean_delivery_min,
    ROUND(baseline_mean, 2) AS baseline_mean,
    ROUND(z_score, 2) AS z_score,
    CASE WHEN is_festival = 1 THEN 'festival' WHEN is_rain = 1 THEN 'rain' ELSE 'unexplained' END AS likely_cause
FROM anomaly_store_day
WHERE ABS(z_score) > 3
ORDER BY scenario, date, store_id;

CREATE OR REPLACE VIEW anomaly_city_flags AS
SELECT
    scenario, city, date,
    ROUND(mean_delivery_min, 2) AS mean_delivery_min,
    ROUND(z_score, 2) AS z_score,
    CASE WHEN is_festival = 1 THEN 'festival' WHEN is_rain = 1 THEN 'rain' ELSE 'unexplained' END AS likely_cause
FROM anomaly_city_day
WHERE ABS(z_score) > 3
ORDER BY scenario, date, city;

-- EXPLORATORY (not pre-registered, added after seeing poor precision): single-day z flags are mostly
-- false alarms. A real local incident tends to last, so keep unexplained flags only when the day
-- before or after was also flagged in the same direction at the same store.
CREATE OR REPLACE VIEW anomaly_incident_candidates AS
WITH scored AS (
    SELECT scenario, store_id, date, is_rain, is_festival, z_score,
        LAG(z_score) OVER (PARTITION BY scenario, store_id ORDER BY date) AS z_yesterday,
        LEAD(z_score) OVER (PARTITION BY scenario, store_id ORDER BY date) AS z_tomorrow
    FROM anomaly_store_day
)
SELECT scenario, store_id, date, ROUND(z_score, 2) AS z_score
FROM scored
WHERE ABS(z_score) > 3
  AND is_rain = 0 AND is_festival = 0
  AND (z_yesterday * z_score > 9 OR z_tomorrow * z_score > 9)
ORDER BY scenario, date, store_id;
