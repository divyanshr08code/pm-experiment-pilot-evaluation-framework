"""Assemble outputs/report.html: one self-contained file with images embedded as base64.

Run: python -m reporting.build_report
"""
import base64
import html
import json

import pandas as pd

from analysis.common import FIGURES, REGISTER_DIR, ROOT, TABLES

FOOTER = "Simulation study. All data are simulated. No number here is an observed real-world result."
LABEL = {"S1_clean_random": "S1 clean random", "S2_worst_stores_selected": "S2 worst stores",
         "S3_city_confounded": "S3 city confounded", "S4_no_true_effect": "S4 no true effect",
         "before_after": "Before/after", "treated_vs_control": "Treated vs control", "did": "Diff-in-diff"}


def values():
    out = {}
    for f in REGISTER_DIR.glob("*.json"):
        for x in json.loads(f.read_text()):
            out[x["id"]] = x["value"]
    return out


def image(name, alt):
    data = base64.b64encode((FIGURES / f"{name}.png").read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{html.escape(alt)}">'


def table(rows, headers):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def main():
    v = values()
    s = pd.read_csv(TABLES / "validation_summary.csv")
    s = s[s.config == "base"]
    method_rows = [[LABEL[r.scenario], LABEL[r.method], f"{r.true_effect:.1f}", f"{r.mean_estimate:.2f}", f"{r.bias:+.2f}",
                    f"{r.coverage_pct:.1f}%", f"{r.significant_pct:.1f}%"] for r in s.itertuples()]
    run_rows = [[LABEL[sc], f"{v[t + '_did']:.2f}", f"[{v[t + '_did_low']:.2f}, {v[t + '_did_high']:.2f}]", f"{v[t + '_perm_p']:.4f}",
                 f"{v[t + '_pretrend_p']:.3f}", f"{v[t + '_guard_idle']} / {v[t + '_guard_refund']}", f"<b>{v[t + '_decision']}</b>"]
                for sc, t in (("S1_clean_random", "s1"), ("S2_worst_stores_selected", "s2"), ("S3_city_confounded", "s3"), ("S4_no_true_effect", "s4"))]
    ab_rows = [[name, f"{v[f'ab_{t}_share_t']:.2f}%", f"{v[f'ab_{t}_srm_p']:.2g}", f"{v[f'ab_{t}_conv_diff']:+.2f} pp [{v[f'ab_{t}_conv_low']:.2f}, {v[f'ab_{t}_conv_high']:.2f}]",
                f"{v[f'ab_{t}_refund_diff']:+.2f} pp", f"<b>{v[f'ab_{t}_decision']}</b>"]
               for name, t in (("Clean lift", "clean"), ("A/A", "aa"), ("SRM bug", "srm"))]

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pilot Evaluation Report</title>
<style>
:root {{ --ink:#0b0b0b; --muted:#52514e; --line:#e6e5e0; --surface:#fcfcfb; --alert:#fdf1d8; }}
body {{ margin:0; background:var(--surface); color:var(--ink); font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:900px; margin:auto; padding:32px 16px 64px; }}
h1 {{ font-size:1.8rem; margin:0 0 8px; }} h2 {{ font-size:1.25rem; margin:40px 0 8px; }}
p {{ margin:8px 0; }} img {{ max-width:100%; height:auto; display:block; margin:12px 0; }}
.banner {{ background:var(--alert); padding:12px 16px; border-radius:6px; }}
.wrap {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:.9rem; margin:12px 0; }}
th,td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); white-space:nowrap; }}
th {{ color:var(--muted); font-weight:600; }}
footer {{ color:var(--muted); font-size:.85rem; margin-top:40px; }}
</style></head><body><main>
<h1>Experiment &amp; Pilot Evaluation Framework</h1>
<p class="banner"><b>Simulation study.</b> All data are simulated, with effects and traps planted on purpose so that each
method can be scored against a known truth. Nothing here describes a real company.</p>

<h2>Recommendation on the simulated pilot: {v['s1_decision']}</h2>
<p>Difference-in-differences estimates {v['s1_did']:.2f} minutes mean delivery time, 95% interval
[{v['s1_did_low']:.2f}, {v['s1_did_high']:.2f}], against a planted {-1.2}. The upper bound clears the pre-registered
minimum worthwhile effect of 0.5 minutes, but only just. Permutation p = {v['s1_perm_p']:.4f}. Guardrails are green.</p>
{table(run_rows, ['Scenario', 'DiD (min)', '95% interval', 'Permutation p', 'Pre-trend p', 'Idle / refund', 'Rubric'])}

<h2>Weekly scorecard</h2>
{image('scorecard', 'Weekly treated and control mean delivery time in S1')}

<h2>Event study: is the before-period gap stable?</h2>
{image('event_study', 'Event study plots for S1 and S2')}
<p>In S2 the gap climbs into the start because the slowest recent stores were picked. The pre-trend check fails on this seed
(p = {v['s2_pretrend_p']:.3f}), but across replications it catches this only {v['val_s2_pretrend_fail']:.1f}% of the time.</p>

<h2>Which methods survive? {int(v['n_reps'])} replications per scenario</h2>
{image('methods_by_scenarios_heatmap', 'Heat-maps of bias and coverage by method and scenario')}
{table(method_rows, ['Scenario', 'Method', 'True', 'Mean estimate', 'Bias', 'Coverage', 'Interval excludes 0'])}
<p>Difference-in-differences holds in S1 and S4, is slightly biased in S2, and <b>fails in S3</b> (bias {v['val_s3_did_bias']:+.2f} min,
coverage {v['val_s3_did_cover']:.1f}%), because a city-level shock hits treated stores more, which breaks parallel trends. Before/after
<i>understates</i> the effect, because planted drift pushes delivery times up; it declares a false effect in {v['val_s4_before_after_signif']:.1f}%
of no-effect runs, against {v['val_s4_did_signif']:.1f}% for DiD.</p>
<p>These conclusions depend on the simulator's assumptions.</p>

<h2>Power</h2>
{image('power_curve', 'Minimum detectable effect by stores per arm and post weeks')}
<p>ICC {v['icc']:.3f} and about {v['avg_cluster_m']:.0f} days per store give a design effect of {v['design_effect']:.1f}. Measured DiD MDE is
{v['did_mde_measured']:.2f} min for 15 stores per arm, against the planning value of 0.735 and {v['val_empirical_mde']:.2f} from replications.</p>

<h2>A/B test</h2>
{table(ab_rows, ['Variant', 'Treatment share', 'SRM p', 'Conversion lift', 'Refund change', 'Ship rule'])}
<p>The clean variant wins on conversion but breaches the refund guardrail, so it does not ship. The SRM variant is invalid before any metric is read.</p>
{image('peeking', 'False-positive rate under daily peeking')}
<p>Under no true effect, stopping at the first daily p &lt; 0.05 falsely declares a win in {v['peek_daily_fpr']:.1f}% of tests, against {v['peek_fixed_fpr']:.1f}% with one fixed-horizon test.</p>
{image('cuped_variance', 'CUPED variance reduction by metric and covariate')}

<footer>{FOOTER} Every number traces to docs/RESULTS.md. Rebuild with <code>bash run_all.sh</code>.</footer>
</main></body></html>"""
    (ROOT / "outputs" / "report.html").write_text(page, encoding="utf-8")
    print("Wrote outputs/report.html")


if __name__ == "__main__":
    main()
