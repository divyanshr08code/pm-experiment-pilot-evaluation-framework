"""Score the pilot methods against the planted truth over 200 simulated replications.

validate/ is the only folder allowed to see the truth. Run: python -m validate.run_validation
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  # one thread each, since the replications run in parallel
os.environ.setdefault("OMP_NUM_THREADS", "1")

import warnings
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import numpy as np
import pandas as pd

from analysis import pilot_estimators as pe
from analysis.common import TABLES, Register
from simulator.config import DEFAULT, SCENARIOS, SEED
from simulator.pilot_panel import simulate_panel, weekly_panel

N_REPS = 200
N_PRECISE = 2000
TAGS = dict(zip(SCENARIOS, ("s1", "s2", "s3", "s4")))
METHODS = ("before_after", "treated_vs_control", "did")

CONFIGS = {
    "base": (DEFAULT, SCENARIOS),
    "effect_half": (replace(DEFAULT, effect_delivery_min=-0.6), SCENARIOS[:3]),
    "noise_x1.5": (replace(DEFAULT, daily_noise_sd=DEFAULT.daily_noise_sd * 1.5, transient_sd=DEFAULT.transient_sd * 1.5), SCENARIOS),
    "s2_zero_effect": (replace(DEFAULT, effect_delivery_min=0.0), SCENARIOS[1:2]),
}


def one_replication(args):
    config, scenario, rep = args
    warnings.simplefilter("ignore")
    params = CONFIGS[config][0]
    seed = np.random.SeedSequence([SEED, SCENARIOS.index(scenario), rep, list(CONFIGS).index(config)]).generate_state(1)[0]
    observed, truth = simulate_panel(scenario, int(seed), base_params=params)
    panel = weekly_panel(observed["store_day_raw"], observed["pilot_assignment"])
    target = truth["effect_delivery_min"]
    row = {"config": config, "scenario": scenario, "rep": rep, "truth": target}
    results = {"before_after": pe.before_after(panel), "treated_vs_control": pe.treated_vs_control(panel),
               "did": pe.did_regression(panel)}
    for name, r in results.items():
        row[f"{name}_est"] = r["est"]
        row[f"{name}_se"] = r["se"]
        row[f"{name}_cover"] = r["low"] <= target <= r["high"]
        row[f"{name}_signif"] = r["low"] > 0 or r["high"] < 0
    pre = pe.pretrend_test(panel)
    row["pretrend_fail"] = pre["p"] < 0.05
    status = {m: pe.guardrail_status(m, pe.did_2x2(panel, m)["did"]) for m in pe.GUARDRAIL_LIMITS}
    row["decision"] = pe.decide(results["did"]["est"], results["did"]["high"], pre["p"], status)
    return row


def precise_replication(args):
    """Fast 2x2-only replication for the high-precision bias check, plus the exploratory
    recent-baseline comparison: what an ops lead would likely do, compare with the last 4 weeks."""
    scenario, rep, zero_effect = args
    params = replace(DEFAULT, effect_delivery_min=0.0) if zero_effect else DEFAULT
    seed = np.random.SeedSequence([SEED, 777, SCENARIOS.index(scenario), rep, int(zero_effect)]).generate_state(1)[0]
    observed, truth = simulate_panel(scenario, int(seed), base_params=params)
    p = weekly_panel(observed["store_day_raw"], observed["pilot_assignment"])
    means = p.groupby(["treated", "week"]).mean_delivery_min.mean().unstack(0)
    post = means.loc[12:20].mean()
    recent = means.loc[7:10].mean()
    return {"scenario": scenario, "zero_effect": zero_effect,
            "did_bias": pe.did_2x2(p)["did"] - truth["effect_delivery_min"],
            "recent_before_after": post[1] - recent[1],
            "recent_did": (post[1] - recent[1]) - (post[0] - recent[0])}


def summarise(raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (config, scenario), g in raw.groupby(["config", "scenario"]):
        truth = g.truth.iloc[0]
        for m in METHODS:
            est = g[f"{m}_est"]
            rows.append({
                "config": config, "scenario": scenario, "method": m, "true_effect": truth,
                "mean_estimate": est.mean(), "bias": est.mean() - truth,
                "bias_mc_error": est.std(ddof=1) / np.sqrt(len(g)),  # how far simulation noise alone could move the bias
                "empirical_sd": est.std(ddof=1), "mean_reported_se": g[f"{m}_se"].mean(),
                "coverage_pct": 100 * g[f"{m}_cover"].mean(), "significant_pct": 100 * g[f"{m}_signif"].mean(),
                "reps": len(g),
            })
    return pd.DataFrame(rows)


def main():
    jobs = [(c, s, r) for c, (_, scenarios) in CONFIGS.items() for s in scenarios for r in range(N_REPS)]
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as pool:
        raw = pd.DataFrame(list(pool.map(one_replication, jobs, chunksize=20)))
    TABLES.mkdir(parents=True, exist_ok=True)
    raw.to_csv(TABLES / "validation_replications.csv", index=False)
    summary = summarise(raw)
    summary.to_csv(TABLES / "validation_summary.csv", index=False)

    decisions = (raw.groupby(["config", "scenario"])["decision"].value_counts(normalize=True).mul(100)
                 .rename("pct").reset_index())
    decisions.to_csv(TABLES / "validation_decisions.csv", index=False)
    pretrend = raw.groupby(["config", "scenario"])["pretrend_fail"].mean().mul(100).rename("pretrend_fail_pct").reset_index()
    pretrend.to_csv(TABLES / "validation_pretrend.csv", index=False)

    reg = Register("validation", "python -m validate.run_validation")
    reg.record("n_reps", N_REPS, "Replications per scenario", "reps")
    base = summary[summary.config == "base"]
    for _, r in base.iterrows():
        key = f"val_{TAGS[r.scenario]}_{r.method}"
        reg.record(f"{key}_bias", r.bias, f"{r.scenario}, {r.method}: bias over {N_REPS} reps", "min")
        reg.record(f"{key}_mean", r.mean_estimate, f"{r.scenario}, {r.method}: mean estimate", "min")
        reg.record(f"{key}_cover", r.coverage_pct, f"{r.scenario}, {r.method}: 95% interval coverage", "%")
        reg.record(f"{key}_signif", r.significant_pct, f"{r.scenario}, {r.method}: share of runs with interval excluding 0", "%")
    reg.record("val_did_mc_error", base[(base.method == "did") & (base.scenario == SCENARIOS[0])].bias_mc_error.iloc[0], "Monte Carlo error of S1 DiD bias", "min")
    s1_did = base[(base.scenario == SCENARIOS[0]) & (base.method == "did")].iloc[0]
    reg.record("val_s1_did_sd", s1_did.empirical_sd, "S1: spread of DiD estimate across replications", "min")
    reg.record("val_s1_did_mean_se", s1_did.mean_reported_se, "S1: average reported clustered SE", "min")
    reg.record("val_empirical_mde", 2.8016 * s1_did.empirical_sd, "Empirical MDE = 2.80 x spread of DiD across replications", "min")

    for _, r in pretrend[pretrend.config == "base"].iterrows():
        reg.record(f"val_{TAGS[r.scenario]}_pretrend_fail", r.pretrend_fail_pct, f"{r.scenario}: pre-trend check fails in this share of runs", "%")
    for _, r in decisions[decisions.config == "base"].iterrows():
        reg.record(f"val_{TAGS[r.scenario]}_decide_{r.decision}", r.pct, f"{r.scenario}: rubric says {r.decision} in this share of runs", "%")

    for config, label in (("effect_half", "eff"), ("noise_x1.5", "noise"), ("s2_zero_effect", "zero")):
        sub = summary[summary.config == config]
        for _, r in sub.iterrows():
            key = f"sens_{label}_{TAGS[r.scenario]}_{r.method}"
            reg.record(f"{key}_bias", r.bias, f"Sensitivity {config}, {r.scenario}, {r.method}: bias", "min")
            reg.record(f"{key}_cover", r.coverage_pct, f"Sensitivity {config}, {r.scenario}, {r.method}: coverage", "%")
            reg.record(f"{key}_signif", r.significant_pct, f"Sensitivity {config}, {r.scenario}, {r.method}: share of runs significant", "%")
        for _, r in decisions[decisions.config == config].iterrows():
            reg.record(f"sens_{label}_{TAGS[r.scenario]}_decide_{r.decision}", r.pct, f"Sensitivity {config}, {r.scenario}: rubric says {r.decision}", "%")
    # 200 replications can only pin a bias down to about +/-0.04 min. This settles small values.
    precise_jobs = [(s, r, False) for s in SCENARIOS[:2] for r in range(N_PRECISE)] + [(SCENARIOS[1], r, True) for r in range(N_PRECISE)]
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as pool:
        precise = pd.DataFrame(list(pool.map(precise_replication, precise_jobs, chunksize=50)))
    reg.record("n_precise", N_PRECISE, "Replications in the high-precision check", "reps")
    for (scenario, zero), g in precise.groupby(["scenario", "zero_effect"]):
        tag = TAGS[scenario] + ("_zero" if zero else "")
        reg.record(f"precise_{tag}_did_bias", g.did_bias.mean(), f"{scenario}, zero_effect={zero}: DiD bias, high precision", "min")
        reg.record(f"precise_{tag}_did_bias_mc", g.did_bias.sem(), f"{scenario}, zero_effect={zero}: Monte Carlo error of that bias", "min")
        reg.record(f"explore_{tag}_recent_ba", g.recent_before_after.mean(), f"EXPLORATORY {scenario}, zero_effect={zero}: before/after using weeks 7-10 as baseline", "min")
        reg.record(f"explore_{tag}_recent_did", g.recent_did.mean(), f"EXPLORATORY {scenario}, zero_effect={zero}: DiD using weeks 7-10 as baseline", "min")
    reg.save()
    print(precise.groupby(["scenario", "zero_effect"])[["did_bias", "recent_before_after", "recent_did"]].mean().round(3))
    pd.set_option("display.width", 200)
    print(summary.drop(columns=["reps"]).round(3).to_string())
    print(decisions.round(1).to_string())
    print(pretrend.round(1).to_string())


if __name__ == "__main__":
    main()
