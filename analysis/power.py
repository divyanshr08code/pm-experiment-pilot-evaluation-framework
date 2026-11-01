"""Power and sample size for store-level pilots.

Two ideas, kept separate on purpose:
1. Design effect. Store-days inside a store are not independent, so a store-day sample is worth
   far fewer independent observations: design effect = 1 + (m - 1) x ICC.
2. DiD power. DiD removes the permanent store level, so what limits it is how much a store's
   average wanders between the pre and post windows.
"""
import numpy as np
import pandas as pd
from scipy import stats

Z_POWER = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)  # 5% two-sided, 80% power


def icc_anova(df: pd.DataFrame, group: str, value: str) -> float:
    """One-way ANOVA estimate of the intra-cluster correlation:
    ICC = (MSB - MSW) / (MSB + (m0 - 1) x MSW), where m0 is the average cluster size adjusted
    for slightly unequal clusters (a few store-days are missing)."""
    groups = df.groupby(group)[value]
    n_i, means = groups.size(), groups.mean()
    k, n = len(n_i), len(df)
    grand = df[value].mean()
    msb = (n_i * (means - grand) ** 2).sum() / (k - 1)
    msw = ((df[value] - df[group].map(means)) ** 2).sum() / (n - k)
    m0 = (n - (n_i**2).sum() / n) / (k - 1)
    return float((msb - msw) / (msb + (m0 - 1) * msw))


def design_effect(m: float, icc: float) -> float:
    return 1 + (m - 1) * icc


def cross_section_mde(sd: float, stores_per_arm: int, m: float, icc: float) -> float:
    """MDE for a simple treated-vs-control comparison of store-day means."""
    return Z_POWER * sd * np.sqrt(2 / (stores_per_arm * m)) * np.sqrt(design_effect(m, icc))


def weekly_residuals(panel: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Store x week table with store and week averages removed (pre-period only)."""
    wide = panel[panel.week <= 10].pivot(index="store_id", columns="week", values=metric)
    return wide.sub(wide.mean(axis=1), axis=0).sub(wide.mean(axis=0), axis=1).add(wide.values.mean())


def ar1_from_placebo(panel: pd.DataFrame, metric: str):
    """Estimate how much weekly store swings persist, from pre-period data only.
    Returns (residual SD, lag-1 correlation). Demeaning over just 10 weeks biases rho downwards,
    so reported MDEs are checked against the empirical spread in validate/."""
    r = weekly_residuals(panel, metric).to_numpy()
    k, t = r.shape
    # Divide by the residual degrees of freedom, not the cell count, since two sets of means were removed.
    var = (r**2).sum() / ((k - 1) * (t - 1))
    rho = (r[:, 1:] * r[:, :-1]).sum() / (r[:, 1:] ** 2).sum()
    return float(np.sqrt(var)), float(rho)


def did_sd_per_store(sd: float, rho: float, pre_weeks: int, post_weeks: int) -> float:
    """SD of one store's (post mean - pre mean) when week-to-week correlation is rho^lag."""
    n = pre_weeks + post_weeks
    lags = np.abs(np.subtract.outer(np.arange(n), np.arange(n)))
    cov = sd**2 * rho**lags
    contrast = np.r_[-np.ones(pre_weeks) / pre_weeks, np.ones(post_weeks) / post_weeks]
    return float(np.sqrt(contrast @ cov @ contrast))


def did_mde(sd_d: float, stores_per_arm: int) -> float:
    return Z_POWER * sd_d * np.sqrt(2 / stores_per_arm)


def stores_needed(sd_d: float, target_mde: float) -> int:
    """Stores per arm so that the MDE is no larger than target_mde."""
    return int(np.ceil(2 * (Z_POWER * sd_d / target_mde) ** 2))
