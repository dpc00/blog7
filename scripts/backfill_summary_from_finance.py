"""One-shot backfill of blog7.db summary tables from finance.db transactions.

Idempotent: INSERT OR IGNORE so existing blog7 summary rows (e.g. recent NS-sync-derived rows)
are preserved; only periods absent from blog7 get filled in from finance.

Run: python scripts/backfill_summary_from_finance.py
"""
import os
import sqlite3
import sys

PHONE_ROOT = "/sdcard/data/finance"
DATA_ROOT = PHONE_ROOT if os.path.isdir(PHONE_ROOT) else os.path.expanduser("~/data/finance")
BLOG7 = os.path.join(DATA_ROOT, "db", "blog7.db")
FINANCE = os.path.join(DATA_ROOT, "db", "finance.db")
print(f"DATA_ROOT={DATA_ROOT}")

ISO_MONDAY = "date(day, '-' || cast((strftime('%w', day) + 6) % 7 as text) || ' days')"

AGGS = [
    ("daily",   "day",                             "day"),
    ("weekly",  ISO_MONDAY,                        "week"),
    ("monthly", "substr(day,1,7)",                 "month"),
    ("yearly",  "substr(day,1,4)",                 "year"),
]

def main():
    if not os.path.exists(BLOG7):  sys.exit(f"missing {BLOG7}")
    if not os.path.exists(FINANCE): sys.exit(f"missing {FINANCE}")

    con = sqlite3.connect(BLOG7)
    con.execute(f"ATTACH DATABASE '{FINANCE}' AS fin")

    for tbl, period_expr, period_col in AGGS:
        before = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        con.execute(f"""
            INSERT OR IGNORE INTO {tbl}
                ({period_col}, asset_id, income, expense, transfer_in, transfer_out, refund_return)
            SELECT {period_expr} AS {period_col}, asset_id,
                   SUM(COALESCE(income,0)),
                   SUM(COALESCE(expense,0)),
                   SUM(COALESCE(transfer_in,0)),
                   SUM(COALESCE(transfer_out,0)),
                   SUM(COALESCE(refund_return,0))
            FROM fin.transactions
            WHERE day IS NOT NULL
            GROUP BY {period_col}, asset_id
        """)
        after = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        rng = con.execute(
            f"SELECT MIN({period_col}), MAX({period_col}) FROM {tbl}"
        ).fetchone()
        print(f"{tbl:8s}: {before} -> {after} rows  range {rng[0]} .. {rng[1]}")

    con.commit()
    con.close()
    print("done.")

if __name__ == "__main__":
    main()
