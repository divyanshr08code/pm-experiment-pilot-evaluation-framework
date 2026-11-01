"""Each estimator must match a library or an independent calculation, and DiD must recover S1's effect."""
import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportions_ztest

from analysis import ab_methods as ab
from analysis import pilot_estimators as pe
from analysis import power as pw
from simulator.pilot_panel import simulate_panel, weekly_panel


def panel_for(scenario, seed):
    obs, truth = simulate_panel(scenario, seed)
    return weekly_panel(obs["store_day_raw"], obs["pilot_assignment"]), truth


def test_did_recovers_effect_in_s1():
    """Across 40 seeds the mean estimate sits on the planted effect, and intervals usually cover it."""
    estimates, covered = [], []
    for seed in range(40):
        p, truth = panel_for("S1_clean_random", 1000 + seed)
        r = pe.did_regression(p)
        estimates.append(r["est"])
        covered.append(r["low"] <= truth["effect_delivery_min"] <= r["high"])
    assert np.mean(estimates) == pytest.approx(-1.2, abs=0.12)
    assert np.mean(covered) >= 0.85


def test_regression_equals_hand_2x2():
    p, _ = panel_for("S1_clean_random", 42)
    assert pe.did_regression(p)["est"] == pytest.approx(pe.did_2x2(p)["did"], abs=1e-9)


def test_clustered_se_matches_store_level_formula():
    p, _ = panel_for("S1_clean_random", 42)
    est, welch_se = pe.did_store_change_se(p)
    r = pe.did_regression(p)
    assert est == pytest.approx(r["est"], abs=1e-9)
    assert r["se"] == pytest.approx(welch_se, rel=0.08)  # differs only by small-sample factors


def test_before_after_matches_scipy_paired_t():
    p, _ = panel_for("S2_worst_stores_selected", 8)
    m = pe.store_period_means(p, "mean_delivery_min").query("treated == 1")
    assert pe.before_after(p)["p"] == pytest.approx(stats.ttest_rel(m.post, m.pre).pvalue, abs=1e-9)


def test_treated_vs_control_matches_scipy_welch():
    p, _ = panel_for("S1_clean_random", 8)
    m = pe.store_period_means(p, "mean_delivery_min")
    lib = stats.ttest_ind(m[m.treated == 1].post, m[m.treated == 0].post, equal_var=False)
    assert pe.treated_vs_control(p)["p"] == pytest.approx(lib.pvalue, abs=1e-9)


def test_permutation_is_close_to_t_test_under_real_effect_and_null():
    p, _ = panel_for("S1_clean_random", 9)
    r = pe.permutation_test(p, draws=2000)
    assert r["est"] == pytest.approx(pe.did_2x2(p)["did"], abs=1e-9)
    assert abs(r["placebo"].mean()) < 0.05
    assert 0 < r["p"] <= 1


def test_event_study_reference_week_is_zero():
    p, _ = panel_for("S1_clean_random", 9)
    e = pe.event_study(p).set_index("week")
    assert e.loc[10, "effect"] == 0
    assert len(e) == 20


@pytest.mark.parametrize("est,high,pre_p,guards,expected", [
    (-1.2, -0.6, 0.5, {"a": "GREEN"}, "SCALE"),
    (-1.2, -0.5, 0.5, {"a": "AMBER"}, "SCALE"),
    (-0.8, -0.2, 0.5, {"a": "GREEN"}, "EXTEND"),
    (-0.8, 0.2, 0.5, {"a": "GREEN"}, "EXTEND"),
    (-0.3, -0.1, 0.5, {"a": "GREEN"}, "ITERATE"),
    (-0.3, 0.2, 0.5, {"a": "GREEN"}, "KILL"),
    (-1.2, -0.6, 0.01, {"a": "GREEN"}, "EXTEND"),
    (-1.2, -0.6, 0.5, {"a": "RED"}, "ITERATE"),
    (-0.2, 0.1, 0.5, {"a": "RED"}, "KILL"),
])
def test_rubric(est, high, pre_p, guards, expected):
    assert pe.decide(est, high, pre_p, guards) == expected


def test_guardrail_thresholds():
    assert pe.guardrail_status("rider_idle_pct", 0.5) == "GREEN"
    assert pe.guardrail_status("rider_idle_pct", 1.5) == "AMBER"
    assert pe.guardrail_status("refund_rate_pct", 0.6) == "RED"


def test_two_proportion_matches_statsmodels():
    r = ab.two_proportion(620, 5000, 560, 5000)
    z, p = proportions_ztest([620, 560], [5000, 5000])
    assert r["z"] == pytest.approx(z) and r["p"] == pytest.approx(p)


def test_srm_matches_scipy():
    r = ab.srm_chi_square(47445, 50063)
    lib = stats.chisquare([47445, 50063])
    assert r["chi2"] == pytest.approx(lib.statistic) and r["p"] == pytest.approx(lib.pvalue)


def test_holm_matches_statsmodels():
    p = {"a": 0.01, "b": 0.04, "c": 0.03}
    ours = ab.holm(p)
    lib = multipletests([0.01, 0.04, 0.03], method="holm")[1]
    assert [ours[k]["holm_p"] for k in "abc"] == pytest.approx(list(lib))


def test_cuped_theta_is_ols_slope_and_removes_corr_squared():
    rng = np.random.default_rng(0)
    x = rng.normal(size=5000)
    y = 2 * x + rng.normal(size=5000)
    adj, theta = ab.cuped(y, x)
    assert theta == pytest.approx(sm.OLS(y, sm.add_constant(x)).fit().params[1])
    assert 1 - adj.var(ddof=1) / y.var(ddof=1) == pytest.approx(np.corrcoef(x, y)[0, 1] ** 2)
    assert adj.mean() == pytest.approx(y.mean())


def test_bootstrap_agrees_with_normal_interval_on_light_tails():
    rng = np.random.default_rng(1)
    a, b = rng.normal(1, 2, 4000), rng.normal(0.8, 2, 4000)
    boot = ab.bootstrap_diff_ci(a, b, draws=800)
    w = ab.welch(a, b)
    assert boot["low"] == pytest.approx(w["low"], abs=0.03) and boot["high"] == pytest.approx(w["high"], abs=0.03)


def test_peeking_inflates_false_positives():
    r = ab.peeking_simulation(n_sims=2000)
    assert 0.03 < r["fixed_horizon_fpr"] < 0.07
    assert r["peeking_fpr"] > 2.5 * r["fixed_horizon_fpr"]


def test_ship_rule_order():
    good = {"low": 0.002}
    win = {"conversion": {"significant": True}}
    assert ab.ship_decision(1e-5, good, win, 0.5, 0.0).startswith("INVALID")
    assert ab.ship_decision(0.5, good, win, 0.01, 0.002).endswith("BREACH")
    assert ab.ship_decision(0.5, good, win, 0.01, -0.002) == "SHIP"
    assert ab.ship_decision(0.5, {"low": 0.0005}, win, 0.5, 0.0).endswith("NO CLEAR WIN")


def test_icc_recovers_known_value():
    rng = np.random.default_rng(2)
    groups = np.repeat(np.arange(200), 40)
    y = rng.normal(0, 1, 200)[groups] + rng.normal(0, 1, len(groups))  # true ICC = 0.5
    assert pw.icc_anova(pd.DataFrame({"g": groups, "y": y}), "g", "y") == pytest.approx(0.5, abs=0.07)


def test_design_effect_and_power_formulas():
    assert pw.design_effect(11, 0.1) == pytest.approx(2.0)
    assert pw.did_mde(1.0, 50) == pytest.approx(2.8016 * np.sqrt(2 / 50), abs=1e-3)
    assert pw.did_sd_per_store(1.0, 0.0, 4, 4) == pytest.approx(np.sqrt(0.5))  # independent weeks
    assert pw.stores_needed(0.75, 0.5) >= 30
