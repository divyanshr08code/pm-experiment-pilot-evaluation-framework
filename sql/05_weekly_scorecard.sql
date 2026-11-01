-- Question: week by week, how do treated and control stores compare on each metric?
-- Grain: weekly_scorecard = scenario x week. weekly_scorecard_inputs keeps the raw sums for the tracker.
-- Metrics: ratio of sums within each group and week. gap = treated - control.
-- All data are simulated.

CREATE OR REPLACE VIEW weekly_scorecard_inputs AS
SELECT
    scenario, week, MIN(period) AS period,
    SUM(orders) FILTER (WHERE treated = 1) AS t_orders,
    SUM(delivery_minutes_total) FILTER (WHERE treated = 1) AS t_delivery_minutes,
    SUM(defective_orders) FILTER (WHERE treated = 1) AS t_defects,
    SUM(rider_idle_minutes) FILTER (WHERE treated = 1) AS t_idle_minutes,
    SUM(rider_shift_minutes) FILTER (WHERE treated = 1) AS t_shift_minutes,
    SUM(refunded_orders) FILTER (WHERE treated = 1) AS t_refunds,
    SUM(orders) FILTER (WHERE treated = 0) AS c_orders,
    SUM(delivery_minutes_total) FILTER (WHERE treated = 0) AS c_delivery_minutes,
    SUM(defective_orders) FILTER (WHERE treated = 0) AS c_defects,
    SUM(rider_idle_minutes) FILTER (WHERE treated = 0) AS c_idle_minutes,
    SUM(rider_shift_minutes) FILTER (WHERE treated = 0) AS c_shift_minutes,
    SUM(refunded_orders) FILTER (WHERE treated = 0) AS c_refunds
FROM stg_store_day
GROUP BY scenario, week
ORDER BY scenario, week;

CREATE OR REPLACE VIEW weekly_scorecard AS
SELECT
    scenario, week, period,
    t_delivery_minutes / t_orders AS treated_delivery_min,
    c_delivery_minutes / c_orders AS control_delivery_min,
    t_delivery_minutes / t_orders - c_delivery_minutes / c_orders AS gap_delivery_min,
    100.0 * t_defects / t_orders - 100.0 * c_defects / c_orders AS gap_defect_pp,
    100.0 * t_idle_minutes / t_shift_minutes - 100.0 * c_idle_minutes / c_shift_minutes AS gap_idle_pp,
    100.0 * t_refunds / t_orders - 100.0 * c_refunds / c_orders AS gap_refund_pp
FROM weekly_scorecard_inputs
ORDER BY scenario, week;
