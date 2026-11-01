"""The tracker must show numbers in any viewer, keep its formulas live, and agree with the analysis."""
import json
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "outputs" / "pilot_tracker.xlsx"
REGISTER = ROOT / "outputs" / "results" / "pilot.json"

pytestmark = pytest.mark.skipif(not (PATH.exists() and REGISTER.exists()), reason="generate the outputs first")


def test_every_formula_keeps_a_stored_result():
    live, stored = load_workbook(PATH), load_workbook(PATH, data_only=True)
    count = 0
    for ws in live:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    count += 1
                    value = stored[ws.title][cell.coordinate].value
                    # A pre-period "effect" is deliberately an empty string, which reads back as None or "".
                    if not (ws.title == "Scorecard" and cell.column_letter in "FHJKMN"):
                        assert value not in (None, ""), f"{ws.title}!{cell.coordinate} has no stored result"
                    assert not str(value).startswith("#"), f"{ws.title}!{cell.coordinate} = {value}"
    assert count > 200


def test_decision_matches_the_python_rubric():
    register = {x["id"]: x["value"] for x in json.loads(REGISTER.read_text())}
    decision = load_workbook(PATH, data_only=True)["Decision"]
    assert decision["B14"].value == register["s1_decision"]
    assert decision["B10"].value == register["s1_guard_idle"]
    assert decision["B11"].value == register["s1_guard_refund"]


def test_pooled_delivery_effect_matches_an_independent_calculation():
    d = pd.read_csv(ROOT / "outputs" / "tables" / "weekly_scorecard.csv")
    d = d[d.scenario == "S1_clean_random"]
    expected = d[d.period == "post"].gap_delivery_min.mean() - d[d.period == "pre"].gap_delivery_min.mean()
    assert load_workbook(PATH, data_only=True)["Scorecard"]["C25"].value == pytest.approx(expected)
