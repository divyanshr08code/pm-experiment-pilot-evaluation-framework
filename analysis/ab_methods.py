"""User-level A/B test methods, each from its plain formula."""
import numpy as np
from scipy import stats


def two_proportion(x_t, n_t, x_c, n_c):
    """Difference in proportions. The test uses the pooled SE (the null says both rates are equal);
    the interval uses the unpooled SE (it describes the rates we actually observed)."""
    p_t, p_c = x_t / n_t, x_c / n_c
    diff = p_t - p_c
    pooled = (x_t + x_c) / (n_t + n_c)
    se_pooled = np.sqrt(pooled * (1 - pooled) * (1 / n_t + 1 / n_c))
    se = np.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)
    z = diff / se_pooled
    return {"p_t": p_t, "p_c": p_c, "diff": diff, "low": diff - 1.96 * se, "high": diff + 1.96 * se,
            "z": z, "p": 2 * stats.norm.sf(abs(z))}


def welch(y_t, y_c):
    """Difference in means with unequal variances; large n, so a normal approximation is enough."""
    diff = y_t.mean() - y_c.mean()
    se = np.sqrt(y_t.var(ddof=1) / len(y_t) + y_c.var(ddof=1) / len(y_c))
    return {"diff": diff, "se": se, "low": diff - 1.96 * se, "high": diff + 1.96 * se,
            "p": 2 * stats.norm.sf(abs(diff / se))}


def bootstrap_diff_ci(y_t, y_c, draws=2000, seed=20261101):
    """Percentile bootstrap: resample users with replacement, recompute the difference, take the
    2.5th and 97.5th percentiles. No normality assumed, which matters with heavy tails."""
    rng = np.random.default_rng(seed)
    diffs = np.empty(draws)
    for i in range(draws):
        diffs[i] = (y_t[rng.integers(0, len(y_t), len(y_t))].mean()
                    - y_c[rng.integers(0, len(y_c), len(y_c))].mean())
    low, high = np.percentile(diffs, [2.5, 97.5])
    return {"low": low, "high": high, "se": diffs.std(ddof=1)}


def cuped(y, x):
    """theta = Cov(Y, X) / Var(X); Y_adj = Y - theta x (X - mean X).
    X is measured before assignment, so the treatment cannot have affected it. Subtracting it
    removes noise, not signal. Variance falls by the share corr(Y, X)^2."""
    theta = np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1)
    return y - theta * (x - x.mean()), theta


def srm_chi_square(n_t, n_c, expected_share=0.5):
    total = n_t + n_c
    e_t, e_c = total * expected_share, total * (1 - expected_share)
    chi2 = (n_t - e_t) ** 2 / e_t + (n_c - e_c) ** 2 / e_c
    return {"chi2": chi2, "p": stats.chi2.sf(chi2, df=1)}


def holm(pvalues: dict, alpha=0.05):
    """Holm step-down: sort p-values; compare the smallest with alpha/m, the next with alpha/(m-1)...
    Adjusted p = running maximum of p x (m - rank), capped at 1."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted, running = {}, 0.0
    for rank, (name, p) in enumerate(items):
        running = max(running, min(1.0, p * (m - rank)))
        adjusted[name] = running
    return {name: {"raw_p": pvalues[name], "holm_p": adjusted[name], "significant": adjusted[name] < alpha}
            for name in pvalues}


def peeking_simulation(n_sims=5000, days=14, users_per_arm_per_day=3571, base_rate=0.12, seed=20261101):
    """A/A test checked every day. Returns the false-positive rate of 'stop at the first p<0.05'
    against that of a single test at the planned end, and the rate by number of looks allowed."""
    rng = np.random.default_rng(seed)
    x_t = rng.binomial(users_per_arm_per_day, base_rate, (n_sims, days)).cumsum(axis=1)
    x_c = rng.binomial(users_per_arm_per_day, base_rate, (n_sims, days)).cumsum(axis=1)
    n = users_per_arm_per_day * np.arange(1, days + 1)
    pooled = (x_t + x_c) / (2 * n)
    z = (x_t - x_c) / n / np.sqrt(pooled * (1 - pooled) * 2 / n)
    reject = 2 * stats.norm.sf(np.abs(z)) < 0.05
    by_day = reject.cumsum(axis=1).astype(bool).mean(axis=0)
    return {"fixed_horizon_fpr": reject[:, -1].mean(), "peeking_fpr": reject.any(axis=1).mean(),
            "cumulative_fpr_by_day": by_day}


def ship_decision(srm_p, conv, holm_result, guardrail_raw_p, guardrail_diff, mwe=0.001):
    """The pre-registered ship rule, in order."""
    if srm_p < 0.001:
        return "INVALID - SRM, FIX ASSIGNMENT"
    if guardrail_diff > 0 and guardrail_raw_p < 0.05:
        return "DO NOT SHIP - GUARDRAIL BREACH"
    if holm_result["conversion"]["significant"] and conv["low"] > mwe:
        return "SHIP"
    return "DO NOT SHIP - NO CLEAR WIN"
