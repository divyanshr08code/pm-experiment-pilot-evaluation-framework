"""Run every sql/NN_*.sql file in order against DuckDB and export the tables used downstream.

Run: python -m analysis.run_sql
"""
import os

import duckdb

from analysis.common import ROOT, TABLES, Register

EXPORTS = ["store_week_panel", "store_day_export", "weekly_scorecard", "weekly_scorecard_inputs", "dq_summary",
           "balance_pre_period", "balance_city", "rank_worst_stores", "ab_srm_check", "anomaly_flags",
           "anomaly_city_flags", "anomaly_incident_candidates"]


def build_connection():
    os.chdir(ROOT)  # the SQL files use paths relative to the project root
    con = duckdb.connect()
    for path in sorted((ROOT / "sql").glob("[0-9]*.sql")):
        con.execute(path.read_text())
    return con


def main():
    con = build_connection()
    TABLES.mkdir(parents=True, exist_ok=True)
    for name in EXPORTS:
        con.execute(f"SELECT * FROM {name}").df().to_csv(TABLES / f"{name}.csv", index=False)

    reg = Register("sql", "python -m analysis.run_sql")
    s1 = "scenario = 'S1_clean_random'"
    q = lambda sql: con.execute(sql).fetchone()[0]
    reg.record("dq_missing_s1", q(f"SELECT missing_store_days FROM dq_summary WHERE {s1}"), "S1 missing store-days found by SQL check", "rows")
    reg.record("dq_dupes_s1", q(f"SELECT duplicated_store_days FROM dq_summary WHERE {s1}"), "S1 duplicated store-days found", "rows")
    reg.record("dq_impossible_s1", q(f"SELECT impossible_rows FROM dq_summary WHERE {s1}"), "S1 impossible rows found", "rows")
    reg.record("clean_rows_s1", q(f"SELECT clean_rows FROM dq_summary WHERE {s1}"), "S1 clean store-day rows after staging", "rows")
    reg.record("flags_s1_total", q(f"SELECT COUNT(*) FROM anomaly_flags WHERE {s1}"), "S1 store-days flagged |z|>3", "days")
    reg.record("flags_s1_unexplained", q(f"SELECT COUNT(*) FROM anomaly_flags WHERE {s1} AND likely_cause='unexplained'"), "S1 flagged store-days with no rain or festival", "days")
    reg.record("flags_s1_rain", q(f"SELECT COUNT(*) FROM anomaly_flags WHERE {s1} AND likely_cause='rain'"), "S1 flagged store-days labelled rain", "days")
    reg.record("flags_s1_festival", q(f"SELECT COUNT(*) FROM anomaly_flags WHERE {s1} AND likely_cause='festival'"), "S1 flagged store-days labelled festival", "days")
    reg.record("city_flags_s1_total", q(f"SELECT COUNT(*) FROM anomaly_city_flags WHERE {s1}"), "S1 city-days flagged |z|>3", "days")
    reg.record("city_flags_s1_unexplained", q(f"SELECT COUNT(*) FROM anomaly_city_flags WHERE {s1} AND likely_cause='unexplained'"), "S1 flagged city-days with no rain or festival", "days")
    for scenario, tag in [("S1_clean_random", "s1"), ("S2_worst_stores_selected", "s2"), ("S3_city_confounded", "s3")]:
        gap = q(f"""SELECT MAX(CASE WHEN treated=1 THEN mean_delivery_min END) - MAX(CASE WHEN treated=0 THEN mean_delivery_min END)
                    FROM balance_pre_period WHERE scenario='{scenario}'""")
        reg.record(f"pre_gap_{tag}", gap, f"{scenario}: pre-period delivery gap treated minus control", "min")
    reg.record("s3_city_a_treated", q("SELECT treated_stores FROM balance_city WHERE scenario='S3_city_confounded' AND city='City_A'"), "S3: treated stores in City_A", "stores")
    reg.save()
    print(con.execute("SELECT * FROM dq_summary").df().to_string())
    print(con.execute("SELECT likely_cause, COUNT(*) n FROM anomaly_flags WHERE scenario='S1_clean_random' GROUP BY 1").df().to_string())
    print(con.execute("SELECT likely_cause, COUNT(*) n FROM anomaly_city_flags WHERE scenario='S1_clean_random' GROUP BY 1").df().to_string())


if __name__ == "__main__":
    main()
