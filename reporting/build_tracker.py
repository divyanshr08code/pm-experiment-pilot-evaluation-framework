"""Build outputs/pilot_tracker.xlsx: inputs are values, everything derived is a live formula.

Only widely supported functions are used (IF, OR, AVERAGEIF, COUNTIF), so the file works
in both Excel and Google Sheets. Run: python -m reporting.build_tracker
"""
import json

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as L

from analysis.common import REGISTER_DIR, ROOT, TABLES

HEAD = PatternFill("solid", fgColor="2A78D6")
INPUT = PatternFill("solid", fgColor="FFF4D6")
GREEN, AMBER, RED = (PatternFill("solid", bgColor=c, fgColor=c) for c in ("BFE8D5", "FBE3A8", "F6C5C4"))
SIM_NOTE = "SIMULATED DATA. This workbook is filled from a simulation study, not a real pilot."


def header(ws, row, values):
    for i, v in enumerate(values, 1):
        c = ws.cell(row, i, v)
        c.fill, c.font = HEAD, Font(bold=True, color="FFFFFF")
        c.alignment = Alignment(wrap_text=True, vertical="center")


def widths(ws, values):
    for i, w in enumerate(values, 1):
        ws.column_dimensions[L(i)].width = w


def build(path=ROOT / "outputs" / "pilot_tracker.xlsx"):
    reg = {x["id"]: x["value"] for x in json.loads((REGISTER_DIR / "pilot.json").read_text())}
    inputs = pd.read_csv(TABLES / "weekly_scorecard_inputs.csv")
    inputs = inputs[inputs.scenario == "S1_clean_random"].sort_values("week")
    wb = Workbook()

    # ---------- Guide ----------
    ws = wb.active
    ws.title = "Guide"
    guide = [SIM_NOTE, "",
             "How to use: paste weekly totals into Inputs (yellow cells). Scorecard and Decision recalculate by themselves.",
             "Tabs: Inputs = raw weekly sums from sql/05_weekly_scorecard.sql | Scorecard = gaps, effect, RAG status |",
             "Rubric = pre-registered thresholds (change only with a dated deviation) | Decision = applies the rubric |",
             "Milestones_Risks = plan and risk log | Status_Update = fill-in template for the weekly note.",
             "Yellow cell = input. Everything else is a formula. See docs/TRACKER_GUIDE.md."]
    for i, t in enumerate(guide, 1):
        ws.cell(i, 1, t)
    ws["A1"].font = Font(bold=True, color="B00020")
    widths(ws, [120])

    # ---------- Inputs ----------
    ws = wb.create_sheet("Inputs")
    cols = ["week", "period", "t_orders", "t_delivery_minutes", "t_defects", "t_idle_minutes", "t_shift_minutes", "t_refunds",
            "c_orders", "c_delivery_minutes", "c_defects", "c_idle_minutes", "c_shift_minutes", "c_refunds"]
    ws["A1"] = SIM_NOTE
    ws["A1"].font = Font(bold=True, color="B00020")
    header(ws, 2, cols)
    for r, row in enumerate(inputs[cols].itertuples(index=False), 3):
        for c, v in enumerate(row, 1):
            cell = ws.cell(r, c, v if isinstance(v, str) else float(v))
            cell.fill = INPUT
    widths(ws, [7, 7] + [14] * 12)
    ws.freeze_panes = "A3"
    first, last = 3, 2 + len(inputs)

    # ---------- Rubric ----------
    ws = wb.create_sheet("Rubric")
    ws["A1"] = "Pre-registered thresholds (docs/PREREGISTRATION.md). " + SIM_NOTE
    ws["A1"].font = Font(bold=True)
    header(ws, 2, ["Item", "Value", "Meaning"])
    rows = [("Minimum worthwhile effect (minutes)", 0.5, "Assumed break-even for the extra packing labour"),
            ("Rider idle: amber above (pp)", 1.0, "DiD worsening"), ("Rider idle: red above (pp)", 2.0, "DiD worsening"),
            ("Refund rate: amber above (pp)", 0.2, "DiD worsening"), ("Refund rate: red above (pp)", 0.5, "DiD worsening"),
            ("Pre-trend p-value floor", 0.05, "Below this the design is not trusted")]
    for i, row in enumerate(rows, 3):
        for j, v in enumerate(row, 1):
            ws.cell(i, j, v)
        ws.cell(i, 2).fill = INPUT
    rules = ["Rubric, applied in order:",
             "1. Pre-trend check fails -> EXTEND (fix the design and re-measure).",
             "2. Any guardrail Red -> KILL if estimate > -MWE, else ITERATE.",
             "3. Interval upper bound <= -MWE -> SCALE through the staged rollout.",
             "4. Estimate <= -MWE, upper bound > -MWE -> EXTEND.",
             "5. Estimate > -MWE and upper bound < 0 -> ITERATE.",
             "6. Otherwise -> KILL.", "",
             "Rollout: 10% -> 25% -> 100% of stores, with holdout stores in the first two stages.",
             "Stop-loss: any guardrail Red for 2 consecutive weeks, or delivery gap vs holdout above 0 for 2 consecutive weeks after the ramp."]
    for i, t in enumerate(rules, 10):
        ws.cell(i, 1, t)
    widths(ws, [42, 10, 60])

    # ---------- Scorecard ----------
    ws = wb.create_sheet("Scorecard")
    ws["A1"] = SIM_NOTE
    ws["A1"].font = Font(bold=True, color="B00020")
    header(ws, 2, ["Week", "Period", "Treated delivery (min)", "Control delivery (min)", "Gap (min)", "Effect vs pre gap (min)",
                   "Defect gap (pp)", "Defect effect (pp)", "Idle gap (pp)", "Idle effect (pp)", "Idle status",
                   "Refund gap (pp)", "Refund effect (pp)", "Refund status", "Reds in a row"])
    ws.row_dimensions[2].height = 45
    n = len(inputs)
    s0, s1 = 3, 2 + n
    for k in range(n):
        r, i = s0 + k, first + k
        ws[f"A{r}"] = f"=Inputs!A{i}"
        ws[f"B{r}"] = f"=Inputs!B{i}"
        ws[f"C{r}"] = f"=Inputs!D{i}/Inputs!C{i}"
        ws[f"D{r}"] = f"=Inputs!J{i}/Inputs!I{i}"
        ws[f"E{r}"] = f"=C{r}-D{r}"
        ws[f"F{r}"] = f'=IF(B{r}="pre","",E{r}-AVERAGEIF($B${s0}:$B${s1},"pre",$E${s0}:$E${s1}))'
        ws[f"G{r}"] = f"=100*Inputs!E{i}/Inputs!C{i}-100*Inputs!K{i}/Inputs!I{i}"
        ws[f"H{r}"] = f'=IF(B{r}="pre","",G{r}-AVERAGEIF($B${s0}:$B${s1},"pre",$G${s0}:$G${s1}))'
        ws[f"I{r}"] = f"=100*Inputs!F{i}/Inputs!G{i}-100*Inputs!L{i}/Inputs!M{i}"
        ws[f"J{r}"] = f'=IF(B{r}="pre","",I{r}-AVERAGEIF($B${s0}:$B${s1},"pre",$I${s0}:$I${s1}))'
        ws[f"K{r}"] = f'=IF(J{r}="","",IF(J{r}>Rubric!$B$5,"RED",IF(J{r}>Rubric!$B$4,"AMBER","GREEN")))'
        ws[f"L{r}"] = f"=100*Inputs!H{i}/Inputs!C{i}-100*Inputs!N{i}/Inputs!I{i}"
        ws[f"M{r}"] = f'=IF(B{r}="pre","",L{r}-AVERAGEIF($B${s0}:$B${s1},"pre",$L${s0}:$L${s1}))'
        ws[f"N{r}"] = f'=IF(M{r}="","",IF(M{r}>Rubric!$B$7,"RED",IF(M{r}>Rubric!$B$6,"AMBER","GREEN")))'
        red_now = f'OR(K{r}="RED",N{r}="RED")'
        ws[f"O{r}"] = f"=IF({red_now},1,0)" if k == 0 else f"=IF({red_now},O{r - 1}+1,0)"
        for col in "CDEFGHIJLM":
            ws[f"{col}{r}"].number_format = "0.00"
    for col in ("K", "N"):
        rng = f"{col}{s0}:{col}{s1}"
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"GREEN"'], fill=GREEN))
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"AMBER"'], fill=AMBER))
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"RED"'], fill=RED))
    ws.conditional_formatting.add(f"O{s0}:O{s1}", FormulaRule(formula=[f"O{s0}>=2"], fill=RED))
    summary_row = s1 + 2
    ws[f"A{summary_row}"] = "Pooled DiD (mean post gap minus mean pre gap)"
    ws[f"A{summary_row}"].font = Font(bold=True)
    labels = [("E", "Delivery (min)"), ("G", "Defects (pp)"), ("I", "Rider idle (pp)"), ("L", "Refunds (pp)")]
    for i, (col, label) in enumerate(labels, 1):
        r = summary_row + i
        ws[f"A{r}"] = label
        ws[f"C{r}"] = f'=AVERAGEIF($B${s0}:$B${s1},"post",{col}{s0}:{col}{s1})-AVERAGEIF($B${s0}:$B${s1},"pre",{col}{s0}:{col}{s1})'
        ws[f"C{r}"].number_format = "0.000"
    ws[f"A{summary_row + 5}"] = ("These are pooled and order-weighted, for weekly monitoring. The formal estimate and interval come "
                                 "from the store-level regression and are entered on the Decision tab.")
    widths(ws, [7, 7] + [11] * 13)
    ws.freeze_panes = "C3"
    pooled_idle, pooled_refund = f"Scorecard!C{summary_row + 3}", f"Scorecard!C{summary_row + 4}"

    # ---------- Decision ----------
    ws = wb.create_sheet("Decision")
    ws["A1"] = "Formal readout. " + SIM_NOTE
    ws["A1"].font = Font(bold=True, color="B00020")
    header(ws, 2, ["Item", "Value", "Source"])
    items = [("DiD estimate, delivery (min)", reg["s1_did"], "analysis/run_pilot.py, store-level regression"),
             ("95% interval lower bound", reg["s1_did_low"], "same"),
             ("95% interval upper bound", reg["s1_did_high"], "same"),
             ("Pre-trend p-value", reg["s1_pretrend_p"], "same"),
             ("DiD rider idle (pp)", reg["s1_idle"], "same"),
             ("DiD refund rate (pp)", reg["s1_refund"], "same")]
    for i, (a, b, c) in enumerate(items, 3):
        ws.cell(i, 1, a)
        ws.cell(i, 2, round(b, 4)).fill = INPUT
        ws.cell(i, 3, c)
    ws["A10"], ws["B10"] = "Rider idle status", '=IF(B7>Rubric!B5,"RED",IF(B7>Rubric!B4,"AMBER","GREEN"))'
    ws["A11"], ws["B11"] = "Refund status", '=IF(B8>Rubric!B7,"RED",IF(B8>Rubric!B6,"AMBER","GREEN"))'
    ws["A12"], ws["B12"] = "Pre-trend check", '=IF(B6<Rubric!B8,"FAIL","PASS")'
    ws["A14"], ws["B14"] = "DECISION", ('=IF(B12="FAIL","EXTEND",IF(OR(B10="RED",B11="RED"),IF(B3>-Rubric!B3,"KILL","ITERATE"),'
                                        'IF(B5<=-Rubric!B3,"SCALE",IF(B3<=-Rubric!B3,"EXTEND",IF(B5<0,"ITERATE","KILL")))))')
    ws["A14"].font = ws["B14"].font = Font(bold=True, size=13)
    ws["A16"], ws["B16"] = "Weeks with any Red guardrail", f'=COUNTIF(Scorecard!K{s0}:K{s1},"RED")+COUNTIF(Scorecard!N{s0}:N{s1},"RED")'
    ws["A17"], ws["B17"] = "Longest stop-loss streak now", f"=Scorecard!O{s1}"
    ws["A18"], ws["B18"] = "Stop-loss triggered?", '=IF(B17>=2,"YES - STOP","NO")'
    ws["A19"], ws["B19"] = "Pooled idle effect (monitoring)", f"={pooled_idle}"
    ws["A20"], ws["B20"] = "Pooled refund effect (monitoring)", f"={pooled_refund}"
    ws["B19"].number_format = ws["B20"].number_format = "0.000"
    widths(ws, [36, 14, 48])

    # ---------- Milestones and risks ----------
    ws = wb.create_sheet("Milestones_Risks")
    ws["A1"] = "Example plan for the simulated pilot, in pilot weeks. " + SIM_NOTE
    header(ws, 2, ["Milestone", "Owner role", "Due (pilot week)", "Status", "Notes"])
    ms = [("Pre-registration signed off", "Program owner", -4), ("Store assignment drawn at random", "Analyst", -3),
          ("Instrumentation check passed", "Analyst", -2), ("Pre-period baseline frozen", "Analyst", 10),
          ("Pilot go-live", "Store ops lead", 11), ("Ramp-in complete, weekly reviews begin", "Program owner", 12),
          ("Mid-pilot review", "Program owner", 15), ("Final readout and go/no-go meeting", "Program owner", 21)]
    for i, (a, b, c) in enumerate(ms, 3):
        ws.cell(i, 1, a); ws.cell(i, 2, b); ws.cell(i, 3, c)
        ws.cell(i, 4, "Not started").fill = INPUT
    start = 13
    header(ws, start, ["Risk", "Owner role", "Likelihood (1-3)", "Impact (1-3)", "Score", "Mitigation", "Status"])
    risks = [("A city-level shock hits treated stores more", "Analyst", 2, 3, "Stratify assignment by city; check balance table; flag rain weeks"),
             ("Ops leads swap in their worst stores", "Program owner", 2, 3, "Random assignment drawn by analyst; assignment locked"),
             ("Packing labour rises more than assumed", "Store ops lead", 2, 2, "Track labour hours; re-check break-even"),
             ("Rider idle share rises past guardrail", "Fleet lead", 1, 2, "Weekly RAG; stop-loss after 2 red weeks"),
             ("Data pipeline drops or duplicates store-days", "Analyst", 2, 2, "Weekly DQ queries before any metric is read"),
             ("Leadership peeks and calls it early", "Program owner", 3, 2, "Fixed read date in the pre-registration")]
    for i, (a, b, c, d, e) in enumerate(risks, start + 1):
        ws.cell(i, 1, a); ws.cell(i, 2, b); ws.cell(i, 3, c).fill = INPUT; ws.cell(i, 4, d).fill = INPUT
        ws.cell(i, 5, f"=C{i}*D{i}"); ws.cell(i, 6, e); ws.cell(i, 7, "Open").fill = INPUT
    widths(ws, [48, 16, 14, 12, 8, 62, 10])

    # ---------- Status update ----------
    ws = wb.create_sheet("Status_Update")
    ws["A1"] = "Weekly status update template. Numbers pull from the other tabs. " + SIM_NOTE
    ws["A1"].font = Font(bold=True, color="B00020")
    rows = [("Reporting week (last in Inputs)", f"=Scorecard!A{s1}"),
            ("Overall status (type Green / Amber / Red)", "Green"),
            ("Delivery gap this week (min)", f"=Scorecard!E{s1}"),
            ("Effect vs pre-period gap this week (min)", f"=Scorecard!F{s1}"),
            ("Rider idle status this week", f"=Scorecard!K{s1}"),
            ("Refund status this week", f"=Scorecard!N{s1}"),
            ("Stop-loss triggered?", "=Decision!B18"),
            ("Current rubric decision (final only at the read date)", "=Decision!B14"),
            ("Top risk (from Milestones_Risks)", ""), ("Asks of leadership", ""), ("Next steps", "")]
    for i, (a, b) in enumerate(rows, 3):
        ws.cell(i, 1, a)
        c = ws.cell(i, 2, b)
        if not str(b).startswith("="):
            c.fill = INPUT
    ws["B5"].number_format = ws["B6"].number_format = "0.00"
    widths(ws, [52, 40])

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print("Wrote", path)


if __name__ == "__main__":
    build()
