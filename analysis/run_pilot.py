"""Run all store-level methods on the SQL panel for each scenario, without using any truth.

Run: python -m analysis.run_pilot
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from analysis import pilot_estimators as pe
from analysis import power as pw
from analysis.common import TABLES, Register

SCENARIO_TAGS = {"S1_clean_random": "s1", "S2_worst_stores_selected": "s2",
                 "S3_city_confounded": "s3", "S4_no_true_effect": "s4"}
METRIC = "mean_delivery_min"


def evaluate(panel):
    """Everything the rubric needs for one scenario."""
    did = pe.did_regression(panel, METRIC)
    pre = pe.pretrend_test(panel, METRIC)
    guards = {}
    for m in ("rider_idle_pct", "refund_rate_pct"):
        guards[m] = pe.did_regression(panel, m)
    status = {m: pe.guardrail_status(m, g["est"]) for m, g in guards.items()}
    return {
        "before_after": pe.before_after(panel, METRIC),
        "treated_vs_control": pe.treated_vs_control(panel, METRIC),
        "did": did,
        "pretrend": pre,
        "guards": guards,
        "status": status,
        "defect": pe.did_regression(panel, "defect_rate_pct"),
        "decision": pe.decide(did["est"], did["high"], pre["p"], status),
    }


def main():
    reg = Register("pilot", "python -m analysis.run_pilot")
    panel_all = pd.read_csv(TABLES / "store_week_panel.csv")
    rows = []
    for scenario, tag in SCENARIO_TAGS.items():
        panel = panel_all[panel_all.scenario == scenario]
        r = evaluate(panel)
        perm = pe.permutation_test(panel, METRIC)
        for method in ("before_after", "treated_vs_control", "did"):
            x = r[method]
            reg.record(f"{tag}_{method}", x["est"], f"{scenario}: {method} estimate, delivery time, seed run", "min")
            rows.append({"scenario": scenario, "method": method, **{k: x[k] for k in ("est", "se", "low", "high", "p")}})
        reg.record(f"{tag}_did_low", r["did"]["low"], f"{scenario}: DiD 95% lower bound", "min")
        reg.record(f"{tag}_did_high", r["did"]["high"], f"{scenario}: DiD 95% upper bound", "min")
        reg.record(f"{tag}_perm_p", perm["p"], f"{scenario}: permutation p-value", "")
        reg.record(f"{tag}_pretrend_p", r["pretrend"]["p"], f"{scenario}: pre-trend slope p-value", "")
        reg.record(f"{tag}_idle", r["guards"]["rider_idle_pct"]["est"], f"{scenario}: DiD rider idle share", "pp")
        reg.record(f"{tag}_refund", r["guards"]["refund_rate_pct"]["est"], f"{scenario}: DiD refund rate", "pp")
        reg.record(f"{tag}_defect", r["defect"]["est"], f"{scenario}: DiD defect rate", "pp")
        reg.record(f"{tag}_defect_low", r["defect"]["low"], f"{scenario}: DiD defect rate 95% lower bound", "pp")
        reg.record(f"{tag}_defect_high", r["defect"]["high"], f"{scenario}: DiD defect rate 95% upper bound", "pp")
        reg.record(f"{tag}_decision", r["decision"], f"{scenario}: rubric decision")
        reg.record(f"{tag}_guard_idle", r["status"]["rider_idle_pct"], f"{scenario}: rider idle guardrail status")
        reg.record(f"{tag}_guard_refund", r["status"]["refund_rate_pct"], f"{scenario}: refund guardrail status")
        pe.event_study(panel, METRIC).assign(scenario=scenario).to_csv(TABLES / f"event_study_{tag}.csv", index=False)
    pd.DataFrame(rows).to_csv(TABLES / "single_run_methods.csv", index=False)

    # S1 is the pre-registered reading dataset. Spell out the 2x2 by hand.
    s1 = panel_all[panel_all.scenario == "S1_clean_random"]
    cells = pe.did_2x2(s1, METRIC)
    for key in ("treated_pre", "treated_post", "control_pre", "control_post", "did"):
        reg.record(f"s1_2x2_{key}", cells[key], f"S1 2x2 DiD cell: {key}", "min")
    perm = pe.permutation_test(s1, METRIC)
    pd.DataFrame({"placebo": perm["placebo"]}).to_csv(TABLES / "permutation_s1.csv", index=False)
    did = pe.did_regression(s1, METRIC)
    reg.record("s1_did_se", did["se"], "S1 DiD clustered SE on the store-week panel", "min")

    # Ordinary vs clustered standard errors on store-days: same estimate, very different confidence.
    day = pd.read_csv(TABLES / "store_day_export.csv")
    day = day[(day.scenario == "S1_clean_random") & (day.week != 11)].copy()
    day["treated_post"] = day.treated * (day.week >= 12).astype(int)
    formula = "mean_delivery_min ~ treated_post + C(store_id) + C(week)"
    ordinary = smf.ols(formula, data=day).fit()
    clustered = smf.ols(formula, data=day).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(day.store_id)[0]})
    reg.record("s1_day_se_ordinary", ordinary.bse["treated_post"], "S1 store-day DiD ordinary OLS SE", "min")
    reg.record("s1_day_se_clustered", clustered.bse["treated_post"], "S1 store-day DiD SE clustered by store", "min")
    reg.record("s1_day_se_ratio", clustered.bse["treated_post"] / ordinary.bse["treated_post"],
               "How many times too small the ordinary SE is", "x")

    # Power, from S1 pre-period data only, as a planner could do before launch.
    pre_day = day[day.week <= 10]
    icc = pw.icc_anova(pre_day, "store_id", "mean_delivery_min")
    m = pre_day.groupby("store_id").size().mean()
    sd = pre_day.mean_delivery_min.std(ddof=1)
    de = pw.design_effect(m, icc)
    reg.record("icc", icc, "ICC of store-day delivery time, S1 pre-period", "")
    reg.record("avg_cluster_m", m, "Average store-days per store, S1 pre-period", "days")
    reg.record("design_effect", de, "Design effect = 1 + (m-1) x ICC", "x")
    reg.record("effective_days_per_store", m / de, "Effective independent observations per store", "days")
    reg.record("cross_section_mde", pw.cross_section_mde(sd, 15, m, icc), "MDE of a treated-vs-control comparison, 15 per arm", "min")
    reg.record("naive_iid_mde", pw.Z_POWER * sd * np.sqrt(2 / (15 * m)), "MDE if store-days were wrongly treated as independent", "min")

    sd_week, rho = pw.ar1_from_placebo(s1, METRIC)
    sd_d = pw.did_sd_per_store(sd_week, rho, 10, 9)
    reg.record("weekly_resid_sd", sd_week, "Weekly residual SD, S1 pre-period", "min")
    reg.record("weekly_resid_rho", rho, "Lag-1 correlation of weekly residuals, S1 pre-period", "")
    reg.record("sd_d_estimated", sd_d, "Estimated SD of one store's post-pre change", "min")
    reg.record("did_mde_measured", pw.did_mde(sd_d, 15), "Measured DiD MDE, 15 stores per arm, 10 pre + 9 post weeks", "min")
    reg.record("stores_needed_mwe", pw.stores_needed(sd_d, 0.5), "Stores per arm so the MDE reaches 0.5 min", "stores")

    # Power curve grid: more stores helps by sqrt(n). More weeks helps less, because weeks are correlated.
    grid = [{"stores_per_arm": n, "post_weeks": w, "mde": pw.did_mde(pw.did_sd_per_store(sd_week, rho, 10, w), n)}
            for n in range(5, 41) for w in (4, 9, 16)]
    pd.DataFrame(grid).to_csv(TABLES / "power_grid.csv", index=False)
    for n, w in ((10, 9), (15, 4), (15, 16), (30, 9)):
        reg.record(f"mde_{n}stores_{w}wk", pw.did_mde(pw.did_sd_per_store(sd_week, rho, 10, w), n),
                   f"DiD MDE with {n} stores per arm and {w} post weeks", "min")
    reg.save()
    print(pd.DataFrame(rows).round(3).to_string())
    for x in reg.items:
        if x["id"] in ("s1_decision", "s2_decision", "s3_decision", "s4_decision", "s1_perm_p", "icc", "design_effect", "s1_day_se_ratio",
                       "weekly_resid_rho", "did_mde_measured", "stores_needed_mwe", "s1_pretrend_p", "s2_pretrend_p", "s3_pretrend_p", "s4_pretrend_p", "s1_idle", "s1_refund", "s1_defect"):
            print(x["id"], x["value"])


if __name__ == "__main__":
    main()
