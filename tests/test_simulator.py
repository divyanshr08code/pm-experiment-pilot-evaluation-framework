"""The simulator must reproduce a known truth with a fixed seed."""
from dataclasses import replace

import numpy as np
import pandas as pd

from simulator.ab_test import simulate_ab
from simulator.config import DEFAULT
from simulator.pilot_panel import simulate_panel


def test_same_seed_same_data():
    a, _ = simulate_panel("S1_clean_random", 1)
    b, _ = simulate_panel("S1_clean_random", 1)
    pd.testing.assert_frame_equal(a["store_day_raw"], b["store_day_raw"])


def test_planted_effect_is_exactly_what_was_asked_for():
    """Same seed with and without the effect means same noise, so the difference IS the planted effect."""
    with_effect, _ = simulate_panel("S1_clean_random", 7)
    without, _ = simulate_panel("S1_clean_random", 7, base_params=replace(DEFAULT, effect_delivery_min=0.0))
    a, b = with_effect["store_day_raw"], without["store_day_raw"]
    gap = (a.delivery_minutes_total - b.delivery_minutes_total) / a.orders
    treated = with_effect["pilot_assignment"].set_index("store_id").treated
    is_treated = a.store_id.map(treated) == 1
    days = (pd.to_datetime(a.date) - pd.to_datetime(a.date).min()).dt.days
    assert np.allclose(gap[is_treated & (days >= 76)], -1.2, atol=0.01)  # fully ramped
    assert np.allclose(gap[~is_treated], 0, atol=0.01)  # control never moves
    assert np.allclose(gap[days < 70], 0, atol=0.01)  # nothing before the start
    week11 = gap[is_treated & (days >= 70) & (days < 76)]
    assert week11.max() < 0 and week11.min() > -1.2  # ramp is partial during week 11


def test_truth_and_counts():
    obs, truth = simulate_panel("S4_no_true_effect", 3, corrupt=True)
    assert truth["effect_delivery_min"] == 0
    assert len(obs["store_day_raw"]) == 4200 - 6 + 4
    assert obs["pilot_assignment"].treated.sum() == 15
    assert len(truth["incidents"]) == 6


def test_s3_concentrates_treated_stores_and_rain():
    obs, _ = simulate_panel("S3_city_confounded", 5)
    merged = obs["pilot_assignment"].merge(obs["store_dim"], on=["scenario", "store_id"])
    assert merged[merged.city == "City_A"].treated.sum() == 9
    w = obs["city_weather"]
    a = w[w.city == "City_A"]
    assert a.iloc[70:].is_rain.mean() > a.iloc[:70].is_rain.mean() + 0.2


def test_s2_selects_slow_stores():
    obs, _ = simulate_panel("S2_worst_stores_selected", 5)
    d = obs["store_day_raw"].merge(obs["pilot_assignment"], on=["scenario", "store_id"])
    d = d[pd.to_datetime(d.date) < pd.Timestamp("2026-03-16")]  # before the pilot starts
    means = d.groupby("treated")[["delivery_minutes_total", "orders"]].sum()
    rate = means.delivery_minutes_total / means.orders
    assert rate[1] > rate[0] + 0.5


def test_ab_variants():
    clean, t = simulate_ab("clean_lift", 11)
    assert t["true_conversion_lift_pp"] == 0.6 and abs(clean.converted.mean() - 0.123) < 0.005
    _, t_aa = simulate_ab("aa", 11)
    assert t_aa["true_conversion_lift_pp"] == 0
    srm, t_srm = simulate_ab("srm", 11)
    assert (srm.arm == "treatment").sum() + t_srm["srm_users_dropped_from_treatment"] > (srm.arm == "control").sum() - 1000
    assert t_srm["srm_users_dropped_from_treatment"] > 1000
