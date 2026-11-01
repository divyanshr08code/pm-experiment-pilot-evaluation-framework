-- Question: can the raw data be trusted before anything is measured?
-- Grain: dq_missing_store_days = scenario x store x date that should exist but does not;
--        dq_duplicates = scenario x store x date loaded more than once;
--        dq_impossible = raw rows with values that cannot happen;
--        dq_summary = one row per scenario.
-- All data are simulated.

-- Expected rows = every store crossed with every date; LEFT JOIN exposes what never arrived.
CREATE OR REPLACE VIEW dq_missing_store_days AS
WITH expected AS (
    SELECT s.scenario, s.store_id, c.date
    FROM dim_store AS s CROSS JOIN dim_calendar AS c
)
SELECT e.scenario, e.store_id, e.date
FROM expected AS e
LEFT JOIN (SELECT DISTINCT scenario, store_id, CAST(date AS DATE) AS date FROM raw_store_day) AS r
  ON r.scenario = e.scenario AND r.store_id = e.store_id AND r.date = e.date
WHERE r.store_id IS NULL;

CREATE OR REPLACE VIEW dq_duplicates AS
SELECT scenario, store_id, date, COUNT(*) AS copies
FROM raw_store_day
GROUP BY scenario, store_id, date
HAVING COUNT(*) > 1;

CREATE OR REPLACE VIEW dq_impossible AS
SELECT scenario, store_id, date, orders, delivery_minutes_total
FROM raw_store_day
WHERE delivery_minutes_total <= 0
   OR orders <= 0
   OR rider_idle_minutes > rider_shift_minutes
   OR late_orders + missing_item_orders + cancelled_orders > orders;

CREATE OR REPLACE VIEW dq_summary AS
SELECT
    s.scenario,
    (SELECT COUNT(*) FROM dq_missing_store_days AS m WHERE m.scenario = s.scenario) AS missing_store_days,
    (SELECT COUNT(*) FROM dq_duplicates AS d WHERE d.scenario = s.scenario) AS duplicated_store_days,
    (SELECT COUNT(*) FROM dq_impossible AS i WHERE i.scenario = s.scenario) AS impossible_rows,
    (SELECT COUNT(*) FROM stg_store_day AS g WHERE g.scenario = s.scenario) AS clean_rows
FROM (SELECT DISTINCT scenario FROM dim_store) AS s
ORDER BY s.scenario;
