-- Question: how does each store compare with its own recent past?
-- Grain: store_day_baseline = scenario x store x date. store_week_wow = scenario x store x week.
-- Metrics: daily mean delivery = delivery minutes / orders. All data are simulated.

CREATE OR REPLACE VIEW store_day_baseline AS
SELECT
    scenario, store_id, date, treated, period,
    delivery_minutes_total / orders AS mean_delivery_min,
    -- Rolling frame excludes today, so a bad day cannot inflate its own baseline.
    SUM(delivery_minutes_total) OVER w7 / SUM(orders) OVER w7 AS rolling_7d_delivery_min
FROM stg_store_day
WINDOW w7 AS (PARTITION BY scenario, store_id ORDER BY date ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING);

CREATE OR REPLACE VIEW store_week_wow AS
WITH weekly AS (
    SELECT scenario, store_id, week, SUM(delivery_minutes_total) / SUM(orders) AS mean_delivery_min
    FROM stg_store_day
    GROUP BY scenario, store_id, week
)
SELECT
    scenario, store_id, week, mean_delivery_min,
    LAG(mean_delivery_min) OVER (PARTITION BY scenario, store_id ORDER BY week) AS previous_week,
    mean_delivery_min - LAG(mean_delivery_min) OVER (PARTITION BY scenario, store_id ORDER BY week) AS wow_change
FROM weekly;
