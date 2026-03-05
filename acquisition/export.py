"""
export.py — Step 3: Export database to CSV and generate a summary report.

Run after search.py and download.py:
    python export.py

Output:
    qdarchive_export.csv   — submit this via the form
    report.txt             — statistics summary
"""

import csv
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from config import DB_PATH, CSV_PATH, REPORT_PATH
from db import get_connection, summary


# ── CSV export ─────────────────────────────────────────────────────────────────

def export_csv(conn) -> int:
    cursor  = conn.execute("SELECT * FROM projects ORDER BY has_qda_files DESC, id ASC")
    columns = [desc[0] for desc in cursor.description]
    rows    = cursor.fetchall()

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    print(f"[Export] {len(rows)} rows → {CSV_PATH}")
    return len(rows)


# ── Report ─────────────────────────────────────────────────────────────────────

def generate_report(conn):
    lines = []

    def p(text=""):
        print(text)
        lines.append(text)

    stats = summary(conn)

    p("=" * 60)
    p("QDArchive — Part 1 Acquisition Report")
    p(f"Generated : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    p("=" * 60)
    p(f"\nTotal projects collected   : {stats['total']}")
    p(f"Projects with QDA files    : {stats['with_qda']}")
    p(f"Projects with primary data : {stats['with_primary']}")

    p("\nBreakdown by repository:")
    for src, count in stats["by_source"].items():
        p(f"  {src:<32} {count}")

    # QDA file type distribution
    qda_counter: Counter = Counter()
    for (types_json,) in conn.execute(
        "SELECT qda_file_types FROM projects WHERE has_qda_files = 1"
    ):
        for ext in json.loads(types_json or "[]"):
            qda_counter[ext] += 1

    if qda_counter:
        p("\nQDA file type breakdown:")
        for ext, count in qda_counter.most_common():
            p(f"  {ext:<22} {count}")

    # License breakdown
    p("\nTop licenses:")
    for row in conn.execute("""
        SELECT license, COUNT(*) AS n FROM projects
        WHERE license IS NOT NULL AND license != ''
        GROUP BY license ORDER BY n DESC LIMIT 10
    """):
        p(f"  {str(row[0]):<32} {row[1]}")

    p("\n" + "=" * 60)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[Report]  Saved → {REPORT_PATH}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] '{DB_PATH}' not found. Run search.py and download.py first.")
        return

    conn = get_connection(DB_PATH)
    export_csv(conn)
    generate_report(conn)
    conn.close()

    print(f"\n✅ Ready for submission:")
    print(f"   CSV export       → {Path(CSV_PATH).resolve()}")
    print(f"   Downloaded files → {Path('archive').resolve()}")
    print(f"\nTag your release:  git tag part-1-release && git push origin part-1-release")


if __name__ == "__main__":
    main()