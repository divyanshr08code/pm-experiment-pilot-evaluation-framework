"""Build the six charts from saved tables. Every chart carries a 'simulated data' footer.

Run: python -m reporting.figures
"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from analysis.common import FIGURES, REGISTER_DIR, TABLES

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
FOOTER = "Simulation study: all data are simulated, none of this is an observed real-world result."
SCENARIO_LABELS = {"S1_clean_random": "S1 clean random", "S2_worst_stores_selected": "S2 worst stores",
                   "S3_city_confounded": "S3 city confounded", "S4_no_true_effect": "S4 no true effect"}
METHOD_LABELS = {"before_after": "Before/after", "treated_vs_control": "Treated vs control", "did": "Diff-in-diff"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "lines.linewidth": 2,
})


def _finish(fig, name, bottom=0.12):
    fig.text(0.01, 0.01, FOOTER, fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, bottom * 0.4, 1, 1))
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.png", dpi=150)
    plt.close(fig)


def event_study():
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, tag, title in zip(axes, ("s1", "s2"), ("S1 clean random: no steady pre-trend, drop after the start",
                                                   "S2 worst stores: gap climbs before the start")):
        d = pd.read_csv(TABLES / f"event_study_{tag}.csv")
        ax.axhline(0, color=MUTED, lw=1)
        ax.axvspan(10.5, 11.5, color=GRID, alpha=0.7, lw=0)
        ax.fill_between(d.week, d.low, d.high, color=BLUE, alpha=0.15, lw=0)
        ax.plot(d.week, d.effect, color=BLUE, marker="o", ms=4)
        ax.set_title(title, fontsize=10.5, loc="left")
        ax.set_xlabel("Week (ramp-in week 11 shaded; reference week 10)")
        ax.set_xticks(range(2, 21, 2))
    axes[0].set_ylabel("Treated minus control, minutes,\nrelative to week 10")
    _finish(fig, "event_study")


def scorecard():
    d = pd.read_csv(TABLES / "weekly_scorecard.csv")
    d = d[d.scenario == "S1_clean_random"]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axvspan(10.5, 11.5, color=GRID, alpha=0.7, lw=0)
    ax.plot(d.week, d.control_delivery_min, color=ORANGE, marker="o", ms=4, label="Control stores")
    ax.plot(d.week, d.treated_delivery_min, color=BLUE, marker="o", ms=4, label="Treated stores")
    ax.annotate("Festival week: both groups rise", (15, d[d.week == 15].control_delivery_min.iloc[0]),
                xytext=(5.5, d.control_delivery_min.max() - 0.1), color=MUTED, fontsize=9,
                arrowprops={"arrowstyle": "-", "color": MUTED})
    ax.text(20.15, d.control_delivery_min.iloc[-1], "Control", color=MUTED, va="center", fontsize=9)
    ax.text(20.15, d.treated_delivery_min.iloc[-1], "Treated", color=MUTED, va="center", fontsize=9)
    ax.set_xlim(0.5, 21.5)
    ax.set_xticks(range(2, 21, 2))
    ax.set_xlabel("Week (ramp-in week 11 shaded)")
    ax.set_ylabel("Mean delivery time, minutes")
    ax.set_title("Weekly scorecard, S1: treated vs control mean delivery time", loc="left", fontsize=10.5)
    ax.legend(frameon=False, loc="lower left", ncol=2)
    _finish(fig, "scorecard")


def heatmap():
    s = pd.read_csv(TABLES / "validation_summary.csv")
    s = s[s.config == "base"]
    scenarios, methods = list(SCENARIO_LABELS), list(METHOD_LABELS)
    bias = s.pivot(index="method", columns="scenario", values="bias").loc[methods, scenarios]
    cover = s.pivot(index="method", columns="scenario", values="coverage_pct").loc[methods, scenarios]
    cmap = LinearSegmentedColormap.from_list("div", [BLUE, "#f0efec", "#e34948"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    ax = axes[0]
    ax.imshow(bias, cmap=cmap, norm=TwoSlopeNorm(vcenter=0, vmin=-1.8, vmax=1.8), aspect="auto")
    ax.set_title("Bias in minutes (estimate minus planted truth)", loc="left", fontsize=10.5)
    for i in range(3):
        for j in range(4):
            v = bias.iloc[i, j]
            ax.text(j, i, f"{v:+.2f}", ha="center", va="center", color="white" if abs(v) > 1.1 else INK)
    ax2 = axes[1]
    greys = LinearSegmentedColormap.from_list("seq", ["#e34948", "#f6c5c4", "#f0efec"])
    ax2.imshow(cover, cmap=greys, vmin=0, vmax=95, aspect="auto")
    ax2.set_title("Coverage of 95% interval (target 95%)", loc="left", fontsize=10.5)
    for i in range(3):
        for j in range(4):
            v = cover.iloc[i, j]
            ax2.text(j, i, f"{v:.1f}%", ha="center", va="center", color="white" if v < 30 else INK)
    for a in axes:
        a.set_xticks(range(4), [SCENARIO_LABELS[x].replace(" ", "\n", 1) for x in scenarios], fontsize=9)
        a.set_yticks(range(3), [METHOD_LABELS[m] for m in methods])
        a.grid(False)
        a.spines[:].set_visible(False)
        a.tick_params(length=0)
    _finish(fig, "methods_by_scenarios_heatmap", 0.16)


def power_curve():
    g = pd.read_csv(TABLES / "power_grid.csv")
    fig, ax = plt.subplots(figsize=(10, 4))
    colors = {4: ORANGE, 9: BLUE, 16: AQUA}
    for w, sub in g.groupby("post_weeks"):
        ax.plot(sub.stores_per_arm, sub.mde, color=colors[w], label=f"{w} post weeks")
        ax.text(40.4, sub.mde.iloc[-1] + {4: 0.03, 9: 0.0, 16: -0.04}[w], f"{w} wk", va="center", fontsize=9, color=MUTED)
    ax.axhline(0.5, color=MUTED, lw=1, ls="--")
    ax.text(5, 0.52, "Minimum worthwhile effect, 0.5 min", color=MUTED, fontsize=9)
    ax.axvline(15, color=MUTED, lw=1, ls=":")
    ax.text(15.3, g.mde.max() * 0.93, "Planned: 15 per arm", color=MUTED, fontsize=9)
    ax.set_xlim(5, 43)
    ax.set_ylim(0)
    ax.set_xlabel("Stores per arm")
    ax.set_ylabel("Minimum detectable effect, minutes")
    ax.set_title("Power: more stores help steadily; more weeks help less, since weeks are correlated", loc="left", fontsize=10.5)
    ax.legend(frameon=False)
    _finish(fig, "power_curve")


def peeking():
    d = pd.read_csv(TABLES / "peeking.csv")
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(d.day, 100 * d.cumulative_fpr, color=BLUE, marker="o", ms=4, label="Stop at first p < 0.05")
    ax.axhline(5, color=MUTED, lw=1, ls="--")
    ax.text(1, 5.5, "Promised false-positive rate, 5%", color=MUTED, fontsize=9)
    last = d.iloc[-1]
    ax.text(last.day - 0.1, 100 * last.cumulative_fpr + 1, f"{100 * last.cumulative_fpr:.1f}% by day 14", ha="right", fontsize=9, color=MUTED)
    ax.set_ylim(0)
    ax.set_xticks(range(1, 15))
    ax.set_xlabel("Day of the A/A test (no true effect)")
    ax.set_ylabel("Tests falsely declared a win so far, %")
    ax.set_title("Peeking: daily checks on a test with no effect", loc="left", fontsize=10.5)
    _finish(fig, "peeking")


def cuped_chart():
    d = pd.read_csv(TABLES / "cuped.csv")
    labels = {"converted": "Conversion", "revenue": "Revenue per user"}
    fig, ax = plt.subplots(figsize=(10, 3.6))
    y = np.arange(2)
    for offset, (cov, color, label) in zip((-0.17, 0.17), (("raw_spend", BLUE, "X = prior spend"), ("log_spend", ORANGE, "X = log(1 + prior spend)"))):
        sub = d[d.covariate == cov].set_index("metric").loc[list(labels)]
        ax.barh(y + offset, sub.variance_reduction_pct, height=0.3, color=color, label=label)
        for yi, v in zip(y + offset, sub.variance_reduction_pct):
            ax.text(v + 0.08, yi, f"{v:.1f}%", va="center", fontsize=9, color=MUTED)
    ax.set_yticks(y, list(labels.values()))
    ax.invert_yaxis()
    ax.set_xlim(0, 9.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Variance removed by CUPED, %")
    ax.set_title("CUPED: modest variance reduction, because prior spend predicts outcomes only weakly here", loc="left", fontsize=10.5)
    ax.legend(frameon=False, loc="center right")
    _finish(fig, "cuped_variance", 0.18)


def main():
    event_study(); scorecard(); heatmap(); power_curve(); peeking(); cuped_chart()
    print("Figures written to", FIGURES)


if __name__ == "__main__":
    main()
