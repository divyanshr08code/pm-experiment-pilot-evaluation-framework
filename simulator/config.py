"""Every planted number in the simulator lives here, so it can be read in one place.

All of these are assumptions for a simulation study. docs/SIMULATOR_SPEC.md gives a
one-line rationale for each. None of them is measured from a real company.
"""
from dataclasses import dataclass, replace

SEED = 20261101

N_STORES = 30
CITIES = ("City_A", "City_B", "City_C")  # 10 stores each
N_WEEKS = 20
N_DAYS = N_WEEKS * 7
N_TREATED = 15
START_DATE = "2026-01-05"  # a Monday; a label only, the data are simulated

# Week numbers run 1..20; day index runs 0..139.
PILOT_START_DAY = 70  # first day of week 11
RAMP_DAYS = 7  # effect grows linearly over week 11
FESTIVAL_WEEK = 15

SCENARIOS = ("S1_clean_random", "S2_worst_stores_selected", "S3_city_confounded", "S4_no_true_effect")
AB_VARIANTS = ("clean_lift", "aa", "srm")


@dataclass(frozen=True)
class PilotParams:
    # --- true pilot effects (steady state, after the ramp) ---
    effect_delivery_min: float = -1.2
    effect_defect_pp: float = -0.4
    effect_idle_pp: float = 0.3  # faster orders leave riders waiting slightly more
    effect_refund_pp: float = 0.0

    # --- delivery time components (minutes) ---
    base_delivery_min: float = 16.0
    city_offset: tuple = (0.6, 0.0, -0.6)
    store_sd: float = 1.0  # permanent store differences
    transient_sd: float = 0.8  # persistent-but-temporary store swings
    transient_rho: float = 0.7  # week-to-week correlation of those swings
    daily_noise_sd: float = 1.5
    city_trend_per_week: tuple = (0.03, 0.01, -0.01)  # mild city time trends
    rain_prob: float = 0.15
    rain_delivery_min: float = 2.5
    festival_delivery_min: float = 2.0
    weekend_delivery_min: float = 0.4

    # --- orders ---
    festival_order_mult: float = 1.4
    rain_order_mult: float = 1.05
    weekend_order_mult: float = 1.15

    # --- defect rate (share of orders) ---
    base_defect_pp: float = 6.0
    store_defect_sd_pp: float = 0.6
    rain_defect_pp: float = 0.8
    festival_defect_pp: float = 1.0

    # --- guardrails ---
    base_idle_pp: float = 22.0
    store_idle_sd_pp: float = 1.5
    festival_idle_pp: float = -4.0  # busy riders idle less
    daily_idle_noise_pp: float = 1.5
    base_refund_pp: float = 1.5

    # --- S3 only: the treated-heavy city gets far more rain after the start ---
    s3_rain_prob_post: float = 0.55
    s3_treated_per_city: tuple = (9, 3, 3)


DEFAULT = PilotParams()


def params_for(scenario: str, base: PilotParams = DEFAULT) -> PilotParams:
    """S4 is the same world with the pilot switched off."""
    if scenario == "S4_no_true_effect":
        return replace(base, effect_delivery_min=0.0, effect_defect_pp=0.0, effect_idle_pp=0.0, effect_refund_pp=0.0)
    return base


@dataclass(frozen=True)
class ABParams:
    n_users: int = 100_000
    base_conversion: float = 0.12
    true_lift_pp: float = 0.6
    base_refund_pp: float = 1.2
    true_refund_lift_pp: float = 0.15  # the change slightly worsens the guardrail
    pre_spend_mu: float = 5.5  # log-normal, roughly 245 currency units median
    pre_spend_sigma: float = 1.2
    order_value_sigma: float = 0.9  # heavy right tail in test-period revenue
    srm_drop_share: float = 0.05  # bug: 5% of treatment users lost
    srm_drop_below_quantile: float = 0.30  # ...and only among low spenders


AB_DEFAULT = ABParams()
