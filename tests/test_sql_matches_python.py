"""The SQL panel and an independent pandas roll-up must agree, and data-quality views must behave."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from simulator.pilot_panel import weekly_panel

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
OBS = ROOT / "data" / "observed"

pytestmark = pytest.mark.skipif(not (TABLES / "store_week_panel.csv").exists(), reason="run bash run_all.sh first")


def test_sql_panel_matches_pandas():
    raw = pd.read_csv(OBS / "store_day_raw.csv")
    raw = raw[raw.scenario == "S1_clean_random"]
    clean = raw.drop_duplicates(["store_id", "date"])
    clean = clean[(clean.delivery_minutes_total > 0) & (clean.orders > 0)]
    assign = pd.read_csv(OBS / "pilot_assignment.csv")
    ours = weekly_panel(clean, assign[assign.scenario == "S1_clean_random"]).set_index(["store_id", "week"]).sort_index()
    sql = pd.read_csv(TABLES / "store_week_panel.csv")
    sql = sql[sql.scenario == "S1_clean_random"].set_index(["store_id", "week"]).sort_index()
    assert len(sql) == 600
    for col in ("mean_delivery_min", "defect_rate_pct", "rider_idle_pct", "refund_rate_pct"):
        assert np.allclose(ours[col], sql[col], atol=1e-8), col


def test_rates_are_ratio_of_sums_not_average_of_averages():
    """On one store-week: recompute from raw counts. An average of daily means would differ."""
    raw = pd.read_csv(OBS / "store_day_raw.csv")
    r = raw[(raw.scenario == "S1_clean_random") & (raw.store_id == "D05")].drop_duplicates("date")
    r = r[r.delivery_minutes_total > 0].sort_values("date").head(7)
    ratio_of_sums = r.delivery_minutes_total.sum() / r.orders.sum()
    avg_of_ratios = (r.delivery_minutes_total / r.orders).mean()
    sql = pd.read_csv(TABLES / "store_week_panel.csv")
    value = sql[(sql.scenario == "S1_clean_random") & (sql.store_id == "D05") & (sql.week == 1)].mean_delivery_min.iloc[0]
    if len(r[pd.to_datetime(r.date) < "2026-01-12"]) == 7:
        assert value == pytest.approx(ratio_of_sums)
        assert ratio_of_sums != avg_of_ratios


def test_scorecard_has_every_week():
    s = pd.read_csv(TABLES / "weekly_scorecard.csv")
    assert (s.groupby("scenario").week.nunique() == 20).all()
    assert set(s.period) == {"pre", "ramp", "post"}
