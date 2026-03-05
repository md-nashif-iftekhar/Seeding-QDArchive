"""
search.py — Step 1: Search Zenodo and collect metadata into the database.

Run:
    python search.py

Output:
    qdarchive.db   — SQLite database with all collected project metadata

What it does:
    - Queries Zenodo with QDA-specific and qualitative research terms
    - Keeps only open-licensed datasets
    - Saves title, description, license, authors, keywords,
      file types and download links to qdarchive.db
"""

from config import DB_PATH, ALL_QUERIES
from db import init_db, summary
from search import ALL_SEARCHERS


def main():
    print("=" * 60)
    print("QDArchive — Part 1: Data Acquisition")
    print("search.py  — Searching Zenodo")
    print("=" * 60)

    conn = init_db(DB_PATH)

    for searcher in ALL_SEARCHERS:
        try:
            searcher.search(conn, queries=ALL_QUERIES)
        except KeyboardInterrupt:
            print(f"\n[Interrupted] Stopped at {searcher.name}. Progress saved.")
            break
        except Exception as e:
            print(f"[ERROR] {searcher.name}: {e}")

    stats = summary(conn)
    print("\n" + "=" * 60)
    print("SEARCH COMPLETE")
    print(f"  Total projects     : {stats['total']}")
    print(f"  With QDA files     : {stats['with_qda']}")
    print(f"  With primary data  : {stats['with_primary']}")
    print(f"  Database           : {DB_PATH}")
    print("=" * 60)
    print("\nNext step:  python download.py")

    conn.close()


if __name__ == "__main__":
    main()