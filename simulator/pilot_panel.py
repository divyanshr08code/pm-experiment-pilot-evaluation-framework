"""Simulate the store-day pilot panel for one scenario.

simulate_panel() returns observed tables plus a truth dict. Keeping them apart here is what
makes the firewall possible: generate.py writes them to different folders.
"""
import numpy as np
import pandas as pd

from simulator.config import (CITIES, FESTIVAL_WEEK, N_DAYS, N_STORES, N_TREATED, PILOT_START_DAY, RAMP_DAYS,
                              START_DATE, PilotParams, params_for)


def _stores(rng, p: PilotParams) -> pd.DataFrame:
    city_idx = np.repeat(np.arange(3), N_STORES // 3)
    size = rng.choice(["S", "M", "L"], size=N_STORES, p=[0.3, 0.4, 0.3])
    throughput = {"S": 350, "M": 600, "L": 950}  # orders per normal day (assumed)
    return pd.DataFrame({
        "store_id": [f"D{i + 1:02d}" for i in range(N_STORES)],
        "city_idx": city_idx,
        "city": [CITIES[c] for c in city_idx],
        "size_class": size,
        "baseline_throughput": [int(throughput[s] * rng.uniform(0.9, 1.1)) for s in size],
        "store_delivery_effect": rng.normal(0, p.store_sd, N_STORES),
        "store_defect_effect": rng.normal(0, p.store_defect_sd_pp, N_STORES),
        "store_idle_effect": rng.normal(0, p.store_idle_sd_pp, N_STORES),
    })


def _ar1_weekly(rng, p: PilotParams, n_weeks: int) -> np.ndarray:
    """Temporary store swings: a bad patch fades over weeks. This is what makes regression
    to the mean possible. Shape: stores x weeks. Stationary SD = transient_sd."""
    x = np.zeros((N_STORES, n_weeks))
    x[:, 0] = rng.normal(0, p.transient_sd, N_STORES)
    innovation_sd = p.transient_sd * np.sqrt(1 - p.transient_rho**2)
    for w in range(1, n_weeks):
        x[:, w] = p.transient_rho * x[:, w - 1] + rng.normal(0, innovation_sd, N_STORES)
    return x


def _rain(rng, p: PilotParams, scenario: str) -> np.ndarray:
    """Rain is city-level: all stores in a city share the same wet days. Shape: cities x days."""
    prob = np.full((3, N_DAYS), p.rain_prob)
    if scenario == "S3_city_confounded":
        prob[0, PILOT_START_DAY:] = p.s3_rain_prob_post
    return rng.random((3, N_DAYS)) < prob


def _assign(rng, stores: pd.DataFrame, scenario: str, p: PilotParams, recent_score: np.ndarray) -> np.ndarray:
    treated = np.zeros(N_STORES, dtype=bool)
    if scenario == "S2_worst_stores_selected":
        # Ops leads pick the slowest stores on the last 4 pre-period weeks.
        treated[np.argsort(-recent_score)[:N_TREATED]] = True
    elif scenario == "S3_city_confounded":
        for c, n in enumerate(p.s3_treated_per_city):
            idx = stores.index[stores.city_idx == c].to_numpy()
            treated[rng.choice(idx, n, replace=False)] = True
    else:
        treated[rng.choice(N_STORES, N_TREATED, replace=False)] = True
    return treated


def simulate_panel(scenario: str, seed: int, base_params: PilotParams | None = None, corrupt: bool = False):
    """corrupt=True plants data-quality problems for the SQL checks to catch. The 200-replication
    validation runs with corrupt=False, since it is scoring estimators and not the checks."""
    p = params_for(scenario, base_params) if base_params is not None else params_for(scenario)
    rng = np.random.default_rng(seed)
    stores = _stores(rng, p)
    transient = _ar1_weekly(rng, p, 20)
    rain = _rain(rng, p, scenario)

    day = np.arange(N_DAYS)
    week = day // 7 + 1
    weekend = (day % 7) >= 5
    festival = week == FESTIVAL_WEEK
    ramp = np.clip((day - PILOT_START_DAY + 1) / RAMP_DAYS, 0, 1)

    # Stores x days arrays
    city = stores.city_idx.to_numpy()
    rain_sd = rain[city]  # stores x days
    trend = np.array(p.city_trend_per_week)[city][:, None] * (week - 1)
    city_off = np.array(p.city_offset)[city][:, None]
    calendar_effect = p.rain_delivery_min * rain_sd + p.festival_delivery_min * festival + p.weekend_delivery_min * weekend
    no_pilot_delivery = (p.base_delivery_min + city_off + stores.store_delivery_effect.to_numpy()[:, None] + trend
                         + transient[:, week - 1] + calendar_effect)
    noise = rng.normal(0, p.daily_noise_sd, (N_STORES, N_DAYS))

    # S2 selects on what an ops lead sees on a dashboard: weeks 7-10 before any pilot effect.
    pre_window = (week >= 7) & (week <= 10)
    recent_score = (no_pilot_delivery + noise)[:, pre_window].mean(axis=1)
    treated = _assign(rng, stores, scenario, p, recent_score)
    effect_on = treated[:, None] * ramp  # stores x days, 0..1

    # Two one-off local incidents (a power cut, a rider dispute) for the anomaly work.
    incident_stores = rng.choice(N_STORES, 2, replace=False)
    incidents = [(int(incident_stores[0]), 38, 3, 6.0), (int(incident_stores[1]), 101, 3, 6.0)]
    incident_add = np.zeros((N_STORES, N_DAYS))
    for s, d0, n, size in incidents:
        incident_add[s, d0:d0 + n] = size

    delivery = no_pilot_delivery + noise + p.effect_delivery_min * effect_on + incident_add
    delivery = np.maximum(delivery, 5.0)  # floor: nothing arrives in under 5 minutes

    mean_orders = (stores.baseline_throughput.to_numpy()[:, None]
                   * (1 + (p.rain_order_mult - 1) * rain_sd)
                   * (1 + (p.festival_order_mult - 1) * festival)
                   * (1 + (p.weekend_order_mult - 1) * weekend))
    orders = rng.poisson(mean_orders)

    defect_p = (p.base_defect_pp + stores.store_defect_effect.to_numpy()[:, None] + p.rain_defect_pp * rain_sd
                + p.festival_defect_pp * festival + p.effect_defect_pp * effect_on) / 100
    defects = rng.binomial(orders, np.clip(defect_p, 0.001, 0.5))
    # A defect is exactly one of late / missing item / cancelled, in fixed assumed proportions.
    late = rng.binomial(defects, 0.60)
    missing = rng.binomial(defects - late, 0.25 / 0.40)
    cancelled = defects - late - missing

    idle_p = (p.base_idle_pp + stores.store_idle_effect.to_numpy()[:, None] + p.festival_idle_pp * festival
              + p.effect_idle_pp * effect_on + rng.normal(0, p.daily_idle_noise_pp, (N_STORES, N_DAYS))) / 100
    shift_minutes = np.round(orders * 14.0)  # about 14 rider-minutes staffed per order (assumed)
    idle_minutes = np.round(np.clip(idle_p, 0.01, 0.9) * shift_minutes)
    refunds = rng.binomial(orders, (p.base_refund_pp + p.effect_refund_pp * effect_on) / 100)

    dates = pd.date_range(START_DATE, periods=N_DAYS, freq="D")
    store_day = pd.DataFrame({
        "scenario": scenario,
        "store_id": np.repeat(stores.store_id.to_numpy(), N_DAYS),
        "date": np.tile(dates.strftime("%Y-%m-%d").to_numpy(), N_STORES),
        "orders": orders.ravel(),
        # Stored as a total so that any roll-up is a ratio of sums, never an average of averages.
        "delivery_minutes_total": np.round((delivery * orders).ravel(), 1),
        "late_orders": late.ravel(),
        "missing_item_orders": missing.ravel(),
        "cancelled_orders": cancelled.ravel(),
        "rider_idle_minutes": idle_minutes.ravel(),
        "rider_shift_minutes": shift_minutes.ravel(),
        "refunded_orders": refunds.ravel(),
    })

    planted_dq = {"missing_rows": 0, "duplicate_rows": 0, "impossible_rows": 0}
    if corrupt:
        store_day, planted_dq = _corrupt(rng, store_day)

    observed = {
        "store_day_raw": store_day,
        "store_dim": stores[["store_id", "city", "size_class", "baseline_throughput"]].assign(scenario=scenario),
        "pilot_assignment": pd.DataFrame({"scenario": scenario, "store_id": stores.store_id, "treated": treated.astype(int)}),
        "city_weather": pd.DataFrame({
            "scenario": scenario,
            "city": np.repeat(CITIES, N_DAYS),
            "date": np.tile(dates.strftime("%Y-%m-%d").to_numpy(), 3),
            "is_rain": rain.ravel().astype(int),
        }),
    }
    truth = {
        "scenario": scenario,
        "seed": seed,
        "effect_delivery_min": p.effect_delivery_min,
        "effect_defect_pp": p.effect_defect_pp,
        "effect_idle_pp": p.effect_idle_pp,
        "effect_refund_pp": p.effect_refund_pp,
        "incidents": [{"store_id": stores.store_id[s], "date": dates[d0 + i].strftime("%Y-%m-%d"), "added_min": size}
                      for s, d0, n, size in incidents for i in range(n)],
        "planted_dq": planted_dq,
    }
    return observed, truth


def _corrupt(rng, df: pd.DataFrame):
    """Plant realistic pipeline faults: lost rows, double-loaded rows, and bad values."""
    idx = rng.permutation(len(df))
    drop, dup, bad = idx[:6], idx[6:10], idx[10:13]
    df = df.copy()
    df["delivery_minutes_total"] = df["delivery_minutes_total"].astype(float)
    df.iloc[bad, df.columns.get_loc("delivery_minutes_total")] = -1.0
    out = pd.concat([df.drop(df.index[drop]), df.iloc[dup]], ignore_index=True)
    return out, {"missing_rows": 6, "duplicate_rows": 4, "impossible_rows": 3}


def weekly_panel(store_day: pd.DataFrame, assignment: pd.DataFrame) -> pd.DataFrame:
    """Store-week roll-up used inside the replication loop. It mirrors sql/07_store_week_panel.sql;
    tests/test_sql_matches_python.py checks the two agree."""
    d = store_day.copy()
    d["week"] = ((pd.to_datetime(d["date"]) - pd.Timestamp(START_DATE)).dt.days // 7 + 1).astype(int)
    d["defects"] = d.late_orders + d.missing_item_orders + d.cancelled_orders
    g = d.groupby(["store_id", "week"], as_index=False)[
        ["orders", "delivery_minutes_total", "defects", "rider_idle_minutes", "rider_shift_minutes", "refunded_orders"]
    ].sum()
    g["mean_delivery_min"] = g.delivery_minutes_total / g.orders
    g["defect_rate_pct"] = 100 * g.defects / g.orders
    g["rider_idle_pct"] = 100 * g.rider_idle_minutes / g.rider_shift_minutes
    g["refund_rate_pct"] = 100 * g.refunded_orders / g.orders
    g = g.merge(assignment[["store_id", "treated"]], on="store_id")
    return g
