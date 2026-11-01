"""Run the A/B test methods on each variant, without using any truth.

Run: python -m analysis.run_ab
"""
import numpy as np
import pandas as pd

from analysis import ab_methods as ab
from analysis.common import OBSERVED, TABLES, Register


def analyse(df: pd.DataFrame, reg: Register, tag: str, bootstrap=True):
    t, c = df[df.arm == "treatment"], df[df.arm == "control"]
    srm = ab.srm_chi_square(len(t), len(c))
    conv = ab.two_proportion(t.converted.sum(), len(t), c.converted.sum(), len(c))
    refund = ab.two_proportion(t.refunded.sum(), len(t), c.refunded.sum(), len(c))
    rev = ab.welch(t.revenue.to_numpy(), c.revenue.to_numpy())
    h = ab.holm({"conversion": conv["p"], "revenue": rev["p"], "refund": refund["p"]})
    decision = ab.ship_decision(srm["p"], conv, h, refund["p"], refund["diff"])

    reg.record(f"ab_{tag}_n_t", len(t), f"{tag}: users in treatment", "users")
    reg.record(f"ab_{tag}_n_c", len(c), f"{tag}: users in control", "users")
    reg.record(f"ab_{tag}_share_t", 100 * len(t) / len(df), f"{tag}: treatment share", "%")
    reg.record(f"ab_{tag}_srm_chi2", srm["chi2"], f"{tag}: SRM chi-square", "")
    reg.record(f"ab_{tag}_srm_p", srm["p"], f"{tag}: SRM p-value", "")
    reg.record(f"ab_{tag}_conv_t", 100 * conv["p_t"], f"{tag}: treatment conversion", "%")
    reg.record(f"ab_{tag}_conv_c", 100 * conv["p_c"], f"{tag}: control conversion", "%")
    reg.record(f"ab_{tag}_conv_diff", 100 * conv["diff"], f"{tag}: conversion difference", "pp")
    reg.record(f"ab_{tag}_conv_low", 100 * conv["low"], f"{tag}: conversion 95% lower bound", "pp")
    reg.record(f"ab_{tag}_conv_high", 100 * conv["high"], f"{tag}: conversion 95% upper bound", "pp")
    reg.record(f"ab_{tag}_conv_p", conv["p"], f"{tag}: conversion raw p", "")
    reg.record(f"ab_{tag}_conv_holm", h["conversion"]["holm_p"], f"{tag}: conversion Holm p", "")
    reg.record(f"ab_{tag}_rev_diff", rev["diff"], f"{tag}: revenue per user difference", "currency")
    reg.record(f"ab_{tag}_rev_p", rev["p"], f"{tag}: revenue raw p (Welch)", "")
    reg.record(f"ab_{tag}_rev_holm", h["revenue"]["holm_p"], f"{tag}: revenue Holm p", "")
    reg.record(f"ab_{tag}_refund_diff", 100 * refund["diff"], f"{tag}: refund rate difference", "pp")
    reg.record(f"ab_{tag}_refund_low", 100 * refund["low"], f"{tag}: refund 95% lower bound", "pp")
    reg.record(f"ab_{tag}_refund_high", 100 * refund["high"], f"{tag}: refund 95% upper bound", "pp")
    reg.record(f"ab_{tag}_refund_p", refund["p"], f"{tag}: refund raw p", "")
    reg.record(f"ab_{tag}_refund_holm", h["refund"]["holm_p"], f"{tag}: refund Holm p", "")
    reg.record(f"ab_{tag}_decision", decision, f"{tag}: ship rule outcome")
    reg.record(f"ab_{tag}_pre_spend_gap", t.pre_spend.mean() - c.pre_spend.mean(), f"{tag}: pre-period spend, treatment minus control", "currency")

    if bootstrap:
        y_t, y_c = t.revenue.to_numpy(), c.revenue.to_numpy()
        boot = ab.bootstrap_diff_ci(y_t, y_c)
        reg.record(f"ab_{tag}_rev_boot_low", boot["low"], f"{tag}: revenue bootstrap 95% lower", "currency")
        reg.record(f"ab_{tag}_rev_boot_high", boot["high"], f"{tag}: revenue bootstrap 95% upper", "currency")
        reg.record(f"ab_{tag}_rev_welch_low", rev["low"], f"{tag}: revenue Welch 95% lower", "currency")
        reg.record(f"ab_{tag}_rev_welch_high", rev["high"], f"{tag}: revenue Welch 95% upper", "currency")
        srt = np.sort(np.r_[y_t, y_c])[::-1]
        reg.record(f"ab_{tag}_rev_top1pct_share", 100 * srt[: len(srt) // 100].sum() / srt.sum(),
                   f"{tag}: share of revenue from the top 1% of users", "%")
        reg.record(f"ab_{tag}_rev_mean_c", y_c.mean(), f"{tag}: control revenue per user", "currency")
    return {"conv": conv, "rev": rev, "refund": refund, "holm": h, "srm": srm, "decision": decision}


def cuped_table(df: pd.DataFrame, reg: Register):
    """Measured variance reduction for each outcome, with X = raw and X = log(1 + spend)."""
    rows = []
    x_raw = df.pre_spend.to_numpy()
    x_log = np.log1p(x_raw)
    t = (df.arm == "treatment").to_numpy()
    for metric in ("converted", "revenue"):
        y = df[metric].to_numpy(dtype=float)
        for name, x in (("raw_spend", x_raw), ("log_spend", x_log)):
            adj, theta = ab.cuped(y, x)
            reduction = 100 * (1 - adj.var(ddof=1) / y.var(ddof=1))
            before, after = ab.welch(y[t], y[~t]), ab.welch(adj[t], adj[~t])
            rows.append({"metric": metric, "covariate": name, "theta": theta, "variance_reduction_pct": reduction,
                         "diff_before": before["diff"], "se_before": before["se"],
                         "diff_after": after["diff"], "se_after": after["se"]})
            reg.record(f"cuped_{metric}_{name}_reduction", reduction, f"CUPED variance reduction, {metric}, covariate {name}", "%")
            reg.record(f"cuped_{metric}_{name}_theta", theta, f"CUPED theta, {metric}, covariate {name}", "")
            reg.record(f"cuped_{metric}_{name}_diff_after", (100 if metric == "converted" else 1) * after["diff"],
                       f"CUPED-adjusted difference, {metric}, covariate {name}", "pp" if metric == "converted" else "currency")
            reg.record(f"cuped_{metric}_{name}_se_after", (100 if metric == "converted" else 1) * after["se"],
                       f"CUPED-adjusted SE, {metric}, covariate {name}", "pp" if metric == "converted" else "currency")
            reg.record(f"cuped_{metric}_{name}_se_before", (100 if metric == "converted" else 1) * before["se"],
                       f"Unadjusted SE, {metric}", "pp" if metric == "converted" else "currency")
    pd.DataFrame(rows).to_csv(TABLES / "cuped.csv", index=False)
    return rows


def main():
    reg = Register("ab", "python -m analysis.run_ab")
    users = pd.read_csv(OBSERVED / "ab_users.csv")
    results = {}
    for variant, tag in (("clean_lift", "clean"), ("aa", "aa"), ("srm", "srm")):
        df = users[users.variant == variant]
        results[tag] = analyse(df, reg, tag, bootstrap=variant == "clean_lift")
    rows = cuped_table(users[users.variant == "clean_lift"], reg)

    peek = ab.peeking_simulation()
    reg.record("peek_fixed_fpr", 100 * peek["fixed_horizon_fpr"], "A/A false-positive rate, single test at planned end", "%")
    reg.record("peek_daily_fpr", 100 * peek["peeking_fpr"], "A/A false-positive rate, stop at first daily p<0.05 over 14 days", "%")
    reg.record("peek_inflation", peek["peeking_fpr"] / peek["fixed_horizon_fpr"], "Peeking inflation factor", "x")
    pd.DataFrame({"day": np.arange(1, 15), "cumulative_fpr": peek["cumulative_fpr_by_day"]}).to_csv(TABLES / "peeking.csv", index=False)
    reg.save()
    for k, v in results.items():
        print(k, v["decision"], {m: round(v[m]["diff"] * (100 if m != "rev" else 1), 3) for m in ("conv", "rev", "refund")}, "srm p", v["srm"]["p"], v["holm"])
    print(pd.DataFrame(rows).round(4).to_string())
    print({k: float(peek[k]) for k in ("fixed_horizon_fpr", "peeking_fpr")})


if __name__ == "__main__":
    main()
