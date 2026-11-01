"""Planning power calculation written BEFORE any outcome data exists.

It uses only assumed variance components (no data files are read), which is why
its result can go in the pre-registration. Run: python analysis/planning_mde.py
"""
import numpy as np
from scipy import stats

Z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)  # 5% two-sided, 80% power


def did_sd_per_store(sd_ar, rho, sd_week_noise, pre_weeks, post_weeks):
    """SD of one store's (post mean - pre mean) when weekly shocks persist (AR1)."""
    n = pre_weeks + post_weeks
    lags = np.abs(np.subtract.outer(np.arange(n), np.arange(n)))
    cov = sd_ar**2 * rho**lags + sd_week_noise**2 * np.eye(n)
    contrast = np.r_[-np.ones(pre_weeks) / pre_weeks, np.ones(post_weeks) / post_weeks]
    return float(np.sqrt(contrast @ cov @ contrast))


if __name__ == "__main__":
    sd_d = did_sd_per_store(sd_ar=0.8, rho=0.7, sd_week_noise=1.5 / np.sqrt(7), pre_weeks=10, post_weeks=9)
    se = sd_d * np.sqrt(1 / 15 + 1 / 15)
    print(f"planning sd_d per store = {sd_d:.3f} min; SE(DiD, 15 vs 15) = {se:.3f}; MDE = {Z * se:.3f} min")
    print(f"P(CI upper <= -0.5 | true -1.2) = {stats.norm.cdf((1.2 - 0.5) / se - 2.045):.3f}")
    se_ab = np.sqrt(2 * 0.12 * 0.88 / 50_000)
    print(f"A/B SE = {se_ab * 100:.3f}pp; MDE = {Z * se_ab * 100:.3f}pp")
    print(f"Power for +0.6pp = {stats.norm.cdf(0.006 / se_ab - 1.96):.3f}")
