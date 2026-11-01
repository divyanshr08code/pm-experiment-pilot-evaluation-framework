"""Re-derive headline numbers a second, independent way. Any mismatch stops the build.

Run: python -m validate.cross_checks
"""
import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportions_ztest

from analysis import ab_methods as ab
from analysis.common import OBSERVED, REGISTER_DIR, ROOT, TABLES, Register
from analysis.run_sql import build_connection
from simulator.config import DEFAULT


def registered():
    out = {}
    for name in ("pilot", "ab", "validation", "sql"):
        for x in json.loads((REGISTER_DIR / f"{name}.json").read_text()):
            out[x["id"]] = x["value"]
    return out


def main():
    reg = Register("crosschecks", "python -m validate.cross_checks")
    r = registered()
    checks = []

    def check(key, description, reported, second, tol):
        ok = abs(reported - second) <= tol
        checks.append((key, reported, second, ok))
        reg.record(f"xc_{key}", second, f"{description} (reported {reported:.5g}, tolerance {tol})")
        print(f"{'PASS' if ok else 'FAIL'}  {key}: reported {reported:.6g}, second way {second:.6g}")

    # 1. DiD straight from clean store-days in SQL, without the Python panel or a regression.
    con = build_connection()
    sql_did = con.execute("""
        WITH store_week AS (
            SELECT store_id, treated, week, period, SUM(delivery_minutes_total) / SUM(orders) AS y
            FROM stg_store_day WHERE scenario = 'S1_clean_random' AND period <> 'ramp'
            GROUP BY store_id, treated, week, period
        ), store_period AS (
            SELECT store_id, treated, period, AVG(y) AS y FROM store_week GROUP BY store_id, treated, period
        ), cell AS (
            SELECT treated, period, AVG(y) AS y FROM store_period GROUP BY treated, period
        )
        SELECT MAX(y) FILTER (WHERE treated = 1 AND period = 'post') - MAX(y) FILTER (WHERE treated = 1 AND period = 'pre')
             - MAX(y) FILTER (WHERE treated = 0 AND period = 'post') + MAX(y) FILTER (WHERE treated = 0 AND period = 'pre')
        FROM cell""").fetchone()[0]
    check("did_sql", "S1 DiD recomputed in SQL", r["s1_did"], sql_did, 1e-6)

    # 2. Clustered SE from store-level changes, with the small-sample factor written out.
    panel = pd.read_csv(TABLES / "store_week_panel.csv")
    s1 = panel[(panel.scenario == "S1_clean_random") & (panel.week != 11)]
    means = s1.assign(post=s1.week >= 12).pivot_table(index=["store_id", "treated"], columns="post", values="mean_delivery_min")
    change = (means[True] - means[False]).reset_index(name="change")
    t, c = change[change.treated == 1].change, change[change.treated == 0].change
    base_se = np.sqrt(t.var(ddof=1) * (len(t) - 1) / len(t) / len(t) + c.var(ddof=1) * (len(c) - 1) / len(c) / len(c))
    g, n, k = 30, len(s1), 30 + 19 + 1 - 1  # clusters, rows, regression parameters (store + week + beta)
    factor = np.sqrt(g / (g - 1) * (n - 1) / (n - k - 0))
    check("did_se", "S1 clustered SE from store-level changes", r["s1_did_se"], base_se * factor, 0.01)

    # 3. A/B with a library.
    users = pd.read_csv(OBSERVED / "ab_users.csv")
    clean = users[users.variant == "clean_lift"]
    tr, ct = clean[clean.arm == "treatment"], clean[clean.arm == "control"]
    _, p_lib = proportions_ztest([tr.converted.sum(), ct.converted.sum()], [len(tr), len(ct)])
    check("conv_p", "Conversion p-value via statsmodels", r["ab_clean_conv_p"], p_lib, 1e-8)

    # 4. SRM with scipy and the SQL view.
    srm = users[users.variant == "srm"]
    n_t, n_c = (srm.arm == "treatment").sum(), (srm.arm == "control").sum()
    check("srm_chi2_scipy", "SRM chi-square via scipy", r["ab_srm_srm_chi2"], stats.chisquare([n_t, n_c]).statistic, 1e-6)
    sql_chi = con.execute("SELECT chi_square FROM ab_srm_check WHERE variant = 'srm'").fetchone()[0]
    check("srm_chi2_sql", "SRM chi-square via SQL", r["ab_srm_srm_chi2"], sql_chi, 1e-6)

    # 5. CUPED theta as an OLS slope, and variance reduction as corr^2.
    slope = sm.OLS(clean.revenue, sm.add_constant(clean.pre_spend)).fit().params["pre_spend"]
    check("cuped_theta", "CUPED theta as an OLS slope", r["cuped_revenue_raw_spend_theta"], slope, 1e-8)
    corr2 = 100 * np.corrcoef(clean.revenue, clean.pre_spend)[0, 1] ** 2
    check("cuped_reduction", "CUPED variance reduction as corr^2", r["cuped_revenue_raw_spend_reduction"], corr2, 1e-6)

    # 6. Holm with a library.
    p = [r["ab_clean_conv_p"], r["ab_clean_rev_p"], r["ab_clean_refund_p"]]
    lib = multipletests(p, method="holm")[1]
    check("holm", "Holm conversion p via statsmodels", r["ab_clean_conv_holm"], lib[0], 1e-10)

    # 7. ICC from a random-intercept model instead of ANOVA.
    day = pd.read_csv(TABLES / "store_day_export.csv")
    pre = day[(day.scenario == "S1_clean_random") & (day.week <= 10)]
    mixed = smf.mixedlm("mean_delivery_min ~ 1", pre, groups=pre.store_id).fit()
    between = float(mixed.cov_re.iloc[0, 0])
    check("icc", "ICC from a random-intercept model", r["icc"], between / (between + mixed.scale), 0.01)

    # 8. Peeking with a different simulator: correlated normals standing in for the running z-score.
    rng = np.random.default_rng(99)
    z = rng.normal(size=(200_000, 14)).cumsum(axis=1) / np.sqrt(np.arange(1, 15))
    second_fpr = 100 * (np.abs(z) > 1.96).any(axis=1).mean()
    check("peek", "Peeking FPR from a Gaussian random walk", r["peek_daily_fpr"], second_fpr, 1.5)

    # 9. Closed-form S3 DiD bias from the planted inputs, against the 200-run measurement.
    # Extra rain days x rain effect x how much more treated stores sit in the shocked city.
    p3 = DEFAULT
    rain_bias = (p3.s3_rain_prob_post - p3.rain_prob) * p3.rain_delivery_min * (9 / 15 - 1 / 15)
    # Plus the city trend difference: treated tilt towards City_A, averaged between pre and post.
    weeks_apart = np.mean(range(12, 21)) - np.mean(range(1, 11))
    trend_t = (9 * p3.city_trend_per_week[0] + 3 * p3.city_trend_per_week[1] + 3 * p3.city_trend_per_week[2]) / 15
    trend_c = (1 * p3.city_trend_per_week[0] + 7 * p3.city_trend_per_week[1] + 7 * p3.city_trend_per_week[2]) / 15
    closed = rain_bias + (trend_t - trend_c) * weeks_apart
    check("s3_bias", "S3 DiD bias, closed form from planted values", r["val_s3_did_bias"], closed, 0.08)

    # 10. Closed-form before/after drift in S4 (no effect): mean city trend x weeks apart + festival share.
    drift = np.mean(p3.city_trend_per_week) * weeks_apart + p3.festival_delivery_min / 9
    check("s4_ba", "S4 before/after drift, closed form", r["val_s4_before_after_bias"], drift, 0.08)

    reg.save()
    failed = [c[0] for c in checks if not c[3]]
    if failed:
        raise SystemExit(f"Cross-check mismatch: {failed}")
    print(f"All {len(checks)} cross-checks passed.")


if __name__ == "__main__":
    main()
