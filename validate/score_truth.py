"""Score the single seeded run (data quality checks, anomaly flags, SRM) against planted truth.

Run: python -m validate.score_truth
"""
import json

import pandas as pd

from analysis.common import ROOT, TABLES, Register


def main():
    truth = json.loads((ROOT / "data" / "truth" / "truth.json").read_text())
    reg = Register("truth_scores", "python -m validate.score_truth")

    dq = pd.read_csv(TABLES / "dq_summary.csv").set_index("scenario")
    flags = pd.read_csv(TABLES / "anomaly_flags.csv")
    all_found, all_planted, unexplained_total, unexplained_true = 0, 0, 0, 0
    candidates = pd.read_csv(TABLES / "anomaly_incident_candidates.csv")
    cand_total, cand_true = 0, 0
    for scenario, t in truth["pilot"].items():
        planted = t["planted_dq"]
        row = dq.loc[scenario]
        assert row.missing_store_days == planted["missing_rows"], "missing-row check disagrees with what was planted"
        assert row.duplicated_store_days == planted["duplicate_rows"], "duplicate check disagrees with what was planted"
        assert row.impossible_rows == planted["impossible_rows"], "impossible-value check disagrees with what was planted"

        incidents = {(i["store_id"], i["date"]) for i in t["incidents"]}
        sub = flags[flags.scenario == scenario]
        flagged = set(zip(sub.store_id, sub.date.astype(str)))
        unexplained = sub[sub.likely_cause == "unexplained"]
        found = incidents & flagged
        # An incident day that coincides with rain is flagged but labelled rain; count it as found.
        all_found += len(found)
        all_planted += len(incidents)
        unexplained_total += len(unexplained)
        unexplained_true += len(incidents & set(zip(unexplained.store_id, unexplained.date.astype(str))))
        cand = candidates[candidates.scenario == scenario]
        cand_total += len(cand)
        cand_true += len(incidents & set(zip(cand.store_id, cand.date.astype(str))))

    reg.record("dq_all_match", 1, "All planted data-quality faults found exactly, all 4 scenarios (assert passed)", "")
    reg.record("anomaly_incident_days", all_planted, "Planted incident store-days across 4 scenarios", "days")
    reg.record("anomaly_recall", 100 * all_found / all_planted, "Share of planted incident days flagged", "%")
    reg.record("anomaly_unexplained_flags", unexplained_total, "Flags labelled unexplained across 4 scenarios", "days")
    reg.record("anomaly_unexplained_precision", 100 * unexplained_true / unexplained_total,
               "Share of unexplained flags that are real planted incidents", "%")
    reg.record("explore_streak_flags", cand_total, "EXPLORATORY: flags that are part of a same-direction streak of 2+ days", "days")
    reg.record("explore_streak_precision", 100 * cand_true / cand_total, "EXPLORATORY: share of streak flags that are real incidents", "%")
    reg.record("explore_streak_recall", 100 * cand_true / all_planted, "EXPLORATORY: share of incident days caught by the streak rule", "%")
    reg.record("srm_dropped_users", truth["ab"]["srm"]["srm_users_dropped_from_treatment"], "Users the planted SRM bug removed", "users")
    reg.save()
    for x in reg.items:
        print(x["id"], x["value"])


if __name__ == "__main__":
    main()
