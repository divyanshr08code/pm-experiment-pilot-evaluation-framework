"""Simulate the user-level A/B test: clean lift, A/A, and a sample ratio mismatch bug."""
import numpy as np
import pandas as pd
from scipy import stats

from simulator.config import AB_DEFAULT, ABParams


def simulate_ab(variant: str, seed: int, p: ABParams = AB_DEFAULT):
    rng = np.random.default_rng(seed)
    n = p.n_users
    pre_spend = rng.lognormal(p.pre_spend_mu, p.pre_spend_sigma, n)
    z_spend = (np.log(pre_spend) - p.pre_spend_mu) / p.pre_spend_sigma  # standardised engagement
    arm = rng.integers(0, 2, n)  # 1 = treatment, fair coin flip

    has_effect = variant != "aa"
    lift = p.true_lift_pp / 100 if has_effect else 0.0
    refund_lift = p.true_refund_lift_pp / 100 if has_effect else 0.0

    # Engaged users convert more. A probit link keeps the average conversion at base_conversion
    # after accounting for the engagement term, so "12%" means 12%.
    slope = 0.45
    intercept = stats.norm.ppf(p.base_conversion) * np.sqrt(1 + slope**2)
    conv_prob = stats.norm.cdf(intercept + slope * z_spend) + lift * arm
    converted = rng.random(n) < np.clip(conv_prob, 0, 1)

    # Revenue is zero without a conversion and heavy-tailed with one. It scales with past spend.
    order_value = np.exp(5.6 + 0.35 * z_spend + rng.normal(0, p.order_value_sigma, n))
    revenue = np.where(converted, order_value, 0.0)

    refunded = rng.random(n) < (p.base_refund_pp / 100 + refund_lift * arm)

    df = pd.DataFrame({
        "variant": variant,
        "user_id": np.arange(1, n + 1),
        "arm": np.where(arm == 1, "treatment", "control"),
        "pre_spend": np.round(pre_spend, 2),
        "converted": converted.astype(int),
        "revenue": np.round(revenue, 2),
        "refunded": refunded.astype(int),
    })

    dropped = 0
    if variant == "srm":
        # The bug: treatment users on an old app version, who are low spenders, never log.
        # The missing users are not random, so the surviving treatment group looks better.
        cutoff = np.quantile(pre_spend, p.srm_drop_below_quantile)
        at_risk = (arm == 1) & (pre_spend < cutoff)
        share_at_risk = p.srm_drop_share / p.srm_drop_below_quantile
        lose = at_risk & (rng.random(n) < share_at_risk)
        dropped = int(lose.sum())
        df = df.loc[~lose].reset_index(drop=True)

    truth = {
        "variant": variant,
        "seed": seed,
        "true_conversion_lift_pp": p.true_lift_pp if has_effect else 0.0,
        "true_refund_lift_pp": p.true_refund_lift_pp if has_effect else 0.0,
        "srm_users_dropped_from_treatment": dropped,
    }
    return df, truth
