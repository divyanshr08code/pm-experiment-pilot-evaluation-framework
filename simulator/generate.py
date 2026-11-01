"""Write data/observed/ (what an analyst sees) and data/truth/ (the planted answers).

Run: python -m simulator.generate
"""
import json
import shutil
from pathlib import Path

import pandas as pd

from simulator.ab_test import simulate_ab
from simulator.config import AB_VARIANTS, FESTIVAL_WEEK, N_DAYS, SCENARIOS, SEED, START_DATE
from simulator.pilot_panel import simulate_panel

ROOT = Path(__file__).resolve().parents[1]
OBSERVED = ROOT / "data" / "observed"
TRUTH = ROOT / "data" / "truth"


def main():
    for folder in (OBSERVED, TRUTH):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)

    tables: dict[str, list] = {}
    truth = {"pilot": {}, "ab": {}}
    for i, scenario in enumerate(SCENARIOS):
        # Different seed per scenario, so S4 is not merely S1 with the effect subtracted.
        observed, t = simulate_panel(scenario, SEED + i, corrupt=True)
        truth["pilot"][scenario] = t
        for name, df in observed.items():
            tables.setdefault(name, []).append(df)
    for name, parts in tables.items():
        pd.concat(parts, ignore_index=True).to_csv(OBSERVED / f"{name}.csv", index=False)

    dates = pd.date_range(START_DATE, periods=N_DAYS, freq="D")
    week = [i // 7 + 1 for i in range(N_DAYS)]
    pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "week": week,
        "is_weekend": [int(d.day_of_week >= 5) for d in dates],
        "is_festival": [int(w == FESTIVAL_WEEK) for w in week],
    }).to_csv(OBSERVED / "calendar.csv", index=False)

    ab_parts = []
    for i, variant in enumerate(AB_VARIANTS):
        df, t = simulate_ab(variant, SEED + 100 + i)
        ab_parts.append(df)
        truth["ab"][variant] = t
    pd.concat(ab_parts, ignore_index=True).to_csv(OBSERVED / "ab_users.csv", index=False)

    (TRUTH / "truth.json").write_text(json.dumps(truth, indent=2))
    print(f"Wrote simulated data to {OBSERVED} and {TRUTH}")


if __name__ == "__main__":
    main()
