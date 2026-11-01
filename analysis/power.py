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


def placebo_change_sd(panel: pd.DataFrame, metric: str) -> float:
    """Run a fake pilot inside the pre-period: each store's mean in weeks 6-10 minus its mean in
    weeks 1-5. Nothing was launched, so the spread across stores is pure background wobble."""
    wide = panel[panel.week <= 10].pivot(index="store_id", columns="week", values=metric)
    change = wide.loc[:, 6:10].mean(axis=1) - wide.loc[:, 1:5].mean(axis=1)
    return float(change.std(ddof=1))


def week_step_sd(panel: pd.DataFrame, metric: str) -> float:
    """SD across stores of the week-to-week change, after removing each week's common shift."""
    wide = panel[panel.week <= 10].pivot(index="store_id", columns="week", values=metric)
    steps = wide.diff(axis=1).iloc[:, 1:]
    steps = steps.sub(steps.mean(axis=0), axis=1)
    return float(np.sqrt((steps.to_numpy() ** 2).sum() / ((steps.shape[0] - 1) * steps.shape[1])))


def calibrate_ar1(placebo_sd: float, step_sd: float):
    """Find the persistence (rho) and size (sd) of weekly swings that reproduce both measured facts:
    Var(week step) = 2 sd^2 (1 - rho), and the 5-vs-5 placebo spread. Two facts, two unknowns.

    Why not simply correlate residuals with their previous week? That was tried first. Removing each
    store's mean over only 10 weeks pushes the correlation far too low, which made the MDE too small."""
    best = None
    for rho in np.arange(0.0, 0.96, 0.01):
        sd = step_sd / np.sqrt(2 * (1 - rho))
        gap = abs(did_sd_per_store(sd, rho, 5, 5) - placebo_sd)
        if best is None or gap < best[0]:
            best = (gap, sd, rho)
    return float(best[1]), float(best[2])


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
