"""The store-level pilot estimators. Each takes a store-week panel with columns
store_id, week, treated, plus the metric. Pre = weeks 1-10, post = weeks 12-20, week 11 is
dropped as the ramp-in washout (pre-registered).

Every interval here is computed across stores, because the store is what was assigned.
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

PRE_WEEKS = range(1, 11)
POST_WEEKS = range(12, 21)
MWE = 0.5  # minimum worthwhile effect, minutes (pre-registered, assumed)


def store_period_means(panel: pd.DataFrame, metric: str) -> pd.DataFrame:
    """One row per store: its pre mean, its post mean, and the change between them."""
    pre = panel[panel.week.isin(PRE_WEEKS)].groupby("store_id")[metric].mean()
    post = panel[panel.week.isin(POST_WEEKS)].groupby("store_id")[metric].mean()
    treated = panel.groupby("store_id")["treated"].first()
    return pd.DataFrame({"treated": treated, "pre": pre, "post": post, "change": post - pre})


def _t_interval(est, se, df):
    half = stats.t.ppf(0.975, df) * se
    p = 2 * stats.t.sf(abs(est / se), df)
    return {"est": est, "se": se, "low": est - half, "high": est + half, "p": p}


def before_after(panel, metric="mean_delivery_min"):
    """Naive method 1: treated stores' average change. Assumes nothing else changed over time."""
    change = store_period_means(panel, metric).query("treated == 1").change
    return _t_interval(change.mean(), change.std(ddof=1) / np.sqrt(len(change)), len(change) - 1)


def treated_vs_control(panel, metric="mean_delivery_min"):
    """Naive method 2: post-period gap. Assumes the two groups started out identical."""
    m = store_period_means(panel, metric)
    t, c = m[m.treated == 1].post, m[m.treated == 0].post
    va, vb = t.var(ddof=1) / len(t), c.var(ddof=1) / len(c)
    # Welch-Satterthwaite degrees of freedom for unequal variances.
    df = (va + vb) ** 2 / (va**2 / (len(t) - 1) + vb**2 / (len(c) - 1))
    return _t_interval(t.mean() - c.mean(), np.sqrt(va + vb), df)


def did_2x2(panel, metric="mean_delivery_min"):
    """DiD by hand: (treated post - treated pre) - (control post - control pre)."""
    m = store_period_means(panel, metric)
    cells = {"treated_pre": m[m.treated == 1].pre.mean(), "treated_post": m[m.treated == 1].post.mean(),
             "control_pre": m[m.treated == 0].pre.mean(), "control_post": m[m.treated == 0].post.mean()}
    cells["did"] = (cells["treated_post"] - cells["treated_pre"]) - (cells["control_post"] - cells["control_pre"])
    return cells


def did_regression(panel, metric="mean_delivery_min"):
    """DiD as a regression: y = store effect + week effect + beta x (treated x post).

    Store effects absorb permanent differences, week effects absorb shocks common to everyone.
    Errors within a store are correlated over time, so standard errors cluster by store.
    The interval uses t with (stores - 1) degrees of freedom, since stores are the real sample size.
    """
    d = panel[panel.week != 11].copy()
    d["treated_post"] = d.treated * (d.week >= 12).astype(int)
    d["y"] = d[metric]
    fit = smf.ols("y ~ treated_post + C(store_id) + C(week)", data=d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d.store_id)[0]})
    n_stores = d.store_id.nunique()
    return _t_interval(fit.params["treated_post"], fit.bse["treated_post"], n_stores - 1)


def did_store_change_se(panel, metric="mean_delivery_min"):
    """Second route to the same answer: compare store-level changes between groups (Welch).
    On a balanced panel the regression's cluster-robust SE differs from this only by small-sample
    factors, which is what tests/test_estimators.py checks."""
    m = store_period_means(panel, metric)
    t, c = m[m.treated == 1].change, m[m.treated == 0].change
    return t.mean() - c.mean(), np.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c))


def permutation_test(panel, metric="mean_delivery_min", draws=5000, seed=20261101):
    """Reshuffle which stores count as treated. If the pilot did nothing, the real label is just
    one shuffle among many, so the real estimate should look ordinary among the shuffled ones."""
    m = store_period_means(panel, metric)
    change = m.change.to_numpy()
    real_mask = m.treated.to_numpy() == 1
    real = change[real_mask].mean() - change[~real_mask].mean()
    rng = np.random.default_rng(seed)
    n_treated = int(real_mask.sum())
    placebo = np.empty(draws)
    for i in range(draws):
        mask = np.zeros(len(change), dtype=bool)
        mask[rng.choice(len(change), n_treated, replace=False)] = True
        placebo[i] = change[mask].mean() - change[~mask].mean()
    # +1 counts the real assignment as one of the possible shuffles, so p is never exactly 0.
    p = (np.sum(np.abs(placebo) >= abs(real)) + 1) / (draws + 1)
    return {"est": real, "p": p, "placebo": placebo}


def event_study(panel, metric="mean_delivery_min", reference_week=10):
    """Treated-control gap by week, relative to week 10. Before the start it should stay near 0."""
    d = panel.copy()
    d["y"] = d[metric]
    weeks = [w for w in sorted(d.week.unique()) if w != reference_week]
    for w in weeks:
        d[f"tw_{w}"] = ((d.week == w) & (d.treated == 1)).astype(int)
    formula = "y ~ C(store_id) + C(week) + " + " + ".join(f"tw_{w}" for w in weeks)
    fit = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.store_id)[0]})
    t_crit = stats.t.ppf(0.975, d.store_id.nunique() - 1)
    rows = [{"week": reference_week, "effect": 0.0, "low": 0.0, "high": 0.0}]
    for w in weeks:
        b, se = fit.params[f"tw_{w}"], fit.bse[f"tw_{w}"]
        rows.append({"week": w, "effect": b, "low": b - t_crit * se, "high": b + t_crit * se})
    return pd.DataFrame(rows).sort_values("week").reset_index(drop=True)


def pretrend_test(panel, metric="mean_delivery_min"):
    """Slope of the treated-control gap across pre-period weeks. p < 0.05 fails the check."""
    d = panel[panel.week.isin(PRE_WEEKS)].copy()
    d["y"] = d[metric]
    d["treated_x_week"] = d.treated * d.week
    fit = smf.ols("y ~ treated_x_week + C(store_id) + C(week)", data=d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d.store_id)[0]})
    slope, se = fit.params["treated_x_week"], fit.bse["treated_x_week"]
    return {"slope": slope, "p": 2 * stats.t.sf(abs(slope / se), d.store_id.nunique() - 1)}


GUARDRAIL_LIMITS = {"rider_idle_pct": (1.0, 2.0), "refund_rate_pct": (0.2, 0.5)}  # (amber above, red above)


def guardrail_status(metric: str, did_est: float) -> str:
    amber, red = GUARDRAIL_LIMITS[metric]
    if did_est > red:
        return "RED"
    return "AMBER" if did_est > amber else "GREEN"


def decide(est, high, pretrend_p, guardrails: dict) -> str:
    """The pre-registered rubric, in its pre-registered order. Negative est = faster delivery."""
    if pretrend_p < 0.05:
        return "EXTEND"
    if "RED" in guardrails.values():
        return "KILL" if est > -MWE else "ITERATE"
    if high <= -MWE:
        return "SCALE"
    if est <= -MWE:
        return "EXTEND"
    if high < 0:
        return "ITERATE"
    return "KILL"
